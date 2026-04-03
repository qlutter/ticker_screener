from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from src.reporter import generate_json, generate_report
from src.screener import load_tickers, run_screen


def configure_logging(output_dir: Path) -> logging.Logger:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("itp_screener")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(output_dir / "screener.log", mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ticker-file ITP valuation screener")
    parser.add_argument("--ticker-file", default="ticker.txt", help="분석할 티커 목록 파일")
    parser.add_argument(
        "--sort-tickers",
        choices=["keep", "asc", "desc"],
        default="keep",
        help="ticker.txt 로드 후 티커 정렬 방식",
    )
    parser.add_argument("--config", default="config/settings.yaml", help="설정 YAML 파일")
    parser.add_argument("--top", type=int, default=20, help="리포트/콘솔 상위 노출 개수")
    parser.add_argument("--output", default="results", help="결과 저장 디렉터리")
    return parser.parse_args()


def load_settings(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output)
    logger = configure_logging(output_dir)

    settings = load_settings(args.config)
    tickers = load_tickers(args.ticker_file, sort_mode=args.sort_tickers)

    if not tickers:
        logger.error("분석할 티커가 없습니다. ticker.txt 내용을 확인하세요.")
        return 1

    preview = ", ".join(tickers[:10]) + (" ..." if len(tickers) > 10 else "")
    logger.info("티커 %d개 로드 완료: %s", len(tickers), preview)
    logger.info("분석 시작")

    results = run_screen(tickers=tickers, settings=settings, logger=logger)

    if not results:
        logger.error("정상적으로 분석된 티커가 없습니다. 로그를 확인하세요.")
        return 2

    report_path = output_dir / "report.html"
    json_path = output_dir / "data.json"

    generate_report(results, str(report_path), top_n=args.top)
    generate_json(results, str(json_path))

    logger.info("\n" + "=" * 90)
    logger.info("TOP %d 시그널 종목", min(args.top, len(results)))
    logger.info("=" * 90)
    for row in results[: args.top]:
        logger.info(
            "%6s | %-30s | P=$%8.2f | ITP=$%8.2f | MOS=%+6.1f%% | Sig=%5.1f | TA=%5.1f | %s",
            row.ticker,
            row.name[:30],
            row.price,
            row.itp,
            row.mos_itp,
            row.signal_score,
            row.ta_score,
            row.zone,
        )

    logger.info("\n리포트: %s", report_path)
    logger.info("JSON:  %s", json_path)
    logger.info("총 %d개 종목 분석 완료", len(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
