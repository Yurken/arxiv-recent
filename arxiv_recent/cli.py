"""CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date

from arxiv_recent.config import get_settings

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _save_digest(md: str, txt: str, run_date: str, cfg: object) -> None:
    """Save rendered digest to local files under data/."""
    from pathlib import Path

    out_dir = Path(cfg.db_full_path).parent  # type: ignore[attr-defined]
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / f"digest-{run_date}.md"
    txt_path = out_dir / f"digest-{run_date}.txt"

    md_path.write_text(md, encoding="utf-8")
    txt_path.write_text(txt, encoding="utf-8")
    logger.info("Digest saved: %s, %s", md_path, txt_path)


def cmd_run(run_date: str | None = None) -> None:
    """Full pipeline: fetch -> summarize -> render -> push."""
    from arxiv_recent.db import Database
    from arxiv_recent.fetcher import fetch_papers
    from arxiv_recent.push import push_digest
    from arxiv_recent.renderer import render_markdown, render_plaintext
    from arxiv_recent.summarizer import summarize_papers

    cfg = get_settings()
    today = run_date or date.today().isoformat()
    db = Database()

    try:
        # Check idempotency
        run = db.get_run(today)
        if run and run["status"] == "sent":
            configured = set(cfg.push_channels)
            already_sent = set(run["sent_channels"].split(",")) if run["sent_channels"] else set()
            if configured and configured.issubset(already_sent):
                logger.info("Run %s already completed and sent, skipping", today)
                return

        # 1. Fetch
        logger.info("Fetching papers...")
        papers = fetch_papers(cfg)
        if not papers:
            logger.warning("No papers fetched, nothing to do")
            db.upsert_run(today, "empty")
            return

        inserted = db.upsert_papers(papers)
        logger.info("Stored %d new papers (%d total fetched)", inserted, len(papers))

        # 2. Summarize
        logger.info("Summarizing papers...")
        summarized = asyncio.run(summarize_papers(papers, db, cfg))
        logger.info("Summarization complete for %d papers", len(summarized))

        # 3. Render & save to local files
        md = render_markdown(summarized, today)
        txt = render_plaintext(summarized, today)
        _save_digest(md, txt, today, cfg)
        logger.info("Rendered digest: %d chars markdown", len(md))

        # 4. Push
        results = push_digest(md, txt, today, cfg)
        sent_channels = [ch for ch, ok in results.items() if ok]
        db.upsert_run(today, "sent" if sent_channels else "rendered", ",".join(sent_channels))

        if sent_channels:
            logger.info("Digest pushed via: %s", ", ".join(sent_channels))
        elif cfg.push_channels:
            logger.warning("No push channels succeeded")
        else:
            logger.info("No push channels configured; digest rendered only")

    except Exception:
        logger.exception("Pipeline failed for %s", today)
        db.upsert_run(today, "failed")
        raise
    finally:
        db.close()


def cmd_fetch() -> None:
    """Fetch papers only."""
    from arxiv_recent.db import Database
    from arxiv_recent.fetcher import fetch_papers

    cfg = get_settings()
    db = Database()
    try:
        papers = fetch_papers(cfg)
        inserted = db.upsert_papers(papers)
        logger.info("Fetched %d papers, %d new", len(papers), inserted)
    finally:
        db.close()


def cmd_summarize() -> None:
    """Summarize unsummarized papers."""
    from arxiv_recent.db import Database
    from arxiv_recent.summarizer import summarize_papers

    cfg = get_settings()
    db = Database()
    try:
        papers = db.get_papers_without_summary()
        if not papers:
            logger.info("All papers already summarized")
            return
        logger.info("Summarizing %d papers...", len(papers))
        asyncio.run(summarize_papers(papers, db, cfg))
        logger.info("Done")
    finally:
        db.close()


def cmd_send(run_date: str | None = None) -> None:
    """Render and send the latest digest."""
    from arxiv_recent.db import Database
    from arxiv_recent.push import push_digest
    from arxiv_recent.renderer import render_markdown, render_plaintext

    cfg = get_settings()
    today = run_date or date.today().isoformat()
    db = Database()
    try:
        papers = db.get_all_papers_with_summaries()
        if not papers:
            logger.warning("No summarized papers found")
            return

        # Parse summary_json if stored as string
        for p in papers:
            sj = p.get("summary_json")
            if isinstance(sj, str):
                import json

                try:
                    p["summary"] = json.loads(sj)
                except (json.JSONDecodeError, TypeError):
                    p["summary"] = None
            elif sj is None:
                p["summary"] = None

        md = render_markdown(papers, today)
        txt = render_plaintext(papers, today)
        _save_digest(md, txt, today, cfg)
        results = push_digest(md, txt, today, cfg)
        sent = [ch for ch, ok in results.items() if ok]
        if sent:
            db.mark_sent(today, ",".join(sent))
            logger.info("Sent via: %s", ", ".join(sent))
        else:
            logger.warning("No push channels succeeded or configured")
    finally:
        db.close()


def cmd_doctor() -> None:
    """Check configuration and connectivity."""
    import httpx

    cfg = get_settings()
    ok = True

    print("=== Configuration Check ===")
    print(f"  Categories: {cfg.arxiv_categories}")
    print(f"  Max papers/day: {cfg.max_papers_per_day}")
    print(f"  Time window: {cfg.time_window_hours}h")
    print(f"  LLM URL: {cfg.vllm_url}")
    print(f"  LLM Model: {cfg.vllm_model_name}")
    print(f"  DB path: {cfg.db_full_path}")
    print(f"  Push channels: {cfg.push_channels}")
    print(f"  Schedule: {cfg.schedule_time} {cfg.schedule_tz}")
    print()

    # Check arXiv
    print("=== Connectivity ===")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://export.arxiv.org/api/query?search_query=cat:cs.AI&max_results=1"
            )
            resp.raise_for_status()
        print("  [OK] arXiv API reachable")
    except Exception as e:
        print(f"  [FAIL] arXiv API: {e}")
        ok = False

    # Check LLM
    try:
        from arxiv_recent.llm import LLMClient

        client = LLMClient(cfg)
        healthy = asyncio.run(client.check_health())
        if healthy:
            print("  [OK] LLM endpoint reachable")
        else:
            print("  [FAIL] LLM endpoint returned empty response")
            ok = False
    except Exception as e:
        print(f"  [FAIL] LLM endpoint: {e}")
        ok = False

    # Check DB
    try:
        from arxiv_recent.db import Database

        db = Database()
        db.close()
        print(f"  [OK] Database writable at {cfg.db_full_path}")
    except Exception as e:
        print(f"  [FAIL] Database: {e}")
        ok = False

    # Check email
    if cfg.email_configured:
        try:
            import smtplib

            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
            print("  [OK] SMTP reachable")
        except Exception as e:
            print(f"  [FAIL] SMTP: {e}")
            ok = False
    else:
        print("  [SKIP] Email not configured")

    # Check QQ
    if cfg.qq_configured:
        try:
            with httpx.Client(timeout=10.0) as hclient:
                resp = hclient.get(f"{cfg.qq_bot_api.rstrip('/')}/get_login_info")
                resp.raise_for_status()
                data = resp.json()
                if data.get("retcode") == 0:
                    nick = data.get("data", {}).get("nickname", "?")
                    print(f"  [OK] QQ bot reachable (nickname: {nick})")
                else:
                    print(f"  [FAIL] QQ bot retcode={data.get('retcode')}")
                    ok = False
        except Exception as e:
            print(f"  [FAIL] QQ bot: {e}")
            ok = False
    else:
        print("  [SKIP] QQ not configured")

    # # Check Telegram（暂时禁用）
    # if cfg.telegram_configured:
    #     try:
    #         with httpx.Client(timeout=10.0) as hclient:
    #             resp = hclient.get(f"https://api.telegram.org/bot{cfg.telegram_bot_token}/getMe")
    #             resp.raise_for_status()
    #         print("  [OK] Telegram bot reachable")
    #     except Exception as e:
    #         print(f"  [FAIL] Telegram: {e}")
    #         ok = False
    # else:
    #     print("  [SKIP] Telegram not configured")

    print()
    if ok:
        print("All checks passed.")
    else:
        print("Some checks failed. Review the output above.")
        sys.exit(1)


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(
        prog="arxiv-recent",
        description="Daily arXiv paper digest with LLM summarization",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    run_parser = sub.add_parser("run", help="Full pipeline: fetch, summarize, push")
    run_parser.add_argument("--date", default=None, help="Run date (YYYY-MM-DD)")

    # fetch
    sub.add_parser("fetch", help="Fetch papers from arXiv")

    # summarize
    sub.add_parser("summarize", help="Summarize unsummarized papers")

    # send
    send_parser = sub.add_parser("send", help="Render and send digest")
    send_parser.add_argument("--date", default=None, help="Run date (YYYY-MM-DD)")

    # doctor
    sub.add_parser("doctor", help="Check config and connectivity")

    # scheduler
    sub.add_parser("scheduler", help="Start daily scheduler")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args.date)
    elif args.command == "fetch":
        cmd_fetch()
    elif args.command == "summarize":
        cmd_summarize()
    elif args.command == "send":
        cmd_send(getattr(args, "date", None))
    elif args.command == "doctor":
        cmd_doctor()
    elif args.command == "scheduler":
        from arxiv_recent.scheduler import start_scheduler

        start_scheduler()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
