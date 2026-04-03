# ITP Ticker Screener

`ticker.txt`에 적은 티커만 분석하는 경량 스크리너입니다.

## 실행

```bash
pip install -r requirements.txt
python main.py --ticker-file ticker.txt --sort-tickers desc --top 20 --output results
```

## 파일 구조

- `ticker.txt`: 분석할 티커 목록
- `config/settings.yaml`: 공통 설정
- `src/screener.py`: 데이터 수집, 지표 계산, 시그널 산출
- `src/reporter.py`: HTML/JSON 리포트 생성
- `.github/workflows/ticker-screener.yml`: GitHub Actions 실행 파일

## 결과 해석

- `ITP`: 통합 목표가
- `Buy Max`: 보수적 매수 상한
- `MOS`: 현재가 대비 할인/프리미엄
- `Signal`: 종합 점수
- `TA`: 기술적 타이밍 점수
- `Zone`
  - `STRONG_BUY`: 가격과 타이밍이 모두 우호적
  - `BUY`: 분할매수 검토 가능
  - `WATCH`: 가치 매력은 있으나 타이밍 추가 확인 필요
  - `HOLD`: 추격보다 관찰 우선

## GitHub Actions

1. 이 폴더 전체를 GitHub 저장소 루트에 업로드
2. `ticker.txt` 수정
3. Actions 탭에서 `Run workflow`
4. 실행 후 `results` 아티팩트 다운로드 또는 Pages 결과 확인
