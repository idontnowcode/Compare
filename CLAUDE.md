# Compare - CLAUDE.md

## 프로젝트 개요
Beyond Compare를 참고하여 만든 Python 기반 데스크탑 파일/폴더 비교 도구.

## 기술 스택
- **언어**: Python 3.11+
- **GUI 프레임워크**: PyQt6
- **diff 알고리즘**: 표준 라이브러리 `difflib.SequenceMatcher`
- **파일 해시**: `hashlib.md5`

## 프로젝트 구조
```
Compare/
├── main.py                  # 앱 진입점
├── requirements.txt         # 의존성
├── CLAUDE.md                # 이 파일
├── FEATURES.md              # 기능 명세서
├── core/
│   ├── __init__.py
│   ├── diff_engine.py       # 텍스트 diff 계산 (LineType, DiffLine, compute_diff)
│   └── folder_scanner.py   # 폴더 재귀 스캔 (FileStatus, FileEntry, scan_folders)
└── ui/
    ├── __init__.py
    ├── main_window.py       # 메인 윈도우 + 탭 관리 + 메뉴
    ├── text_compare.py      # 텍스트 비교 위젯 (DiffPanel, TextCompareWidget)
    └── folder_compare.py   # 폴더 비교 위젯 (FolderCompareWidget)
```

## 실행 방법
```bash
pip install -r requirements.txt
python main.py
```

## 핵심 아키텍처

### diff 흐름
1. `compute_diff(left_text, right_text)` → `(left_lines, right_lines)` 각각 `DiffLine` 리스트
2. `DiffPanel.set_lines()` → `paintEvent`에서 직접 렌더링 (QAbstractScrollArea 기반)
3. 좌/우 패널 스크롤은 `scrolled` 시그널로 동기화

### 폴더 비교 흐름
1. `scan_folders(left_root, right_root)` → `FileEntry` 트리 반환
2. `FolderCompareWidget`이 트리를 QTreeWidget으로 렌더링
3. 파일 더블클릭 → `open_text_compare` 시그널 → 새 텍스트 비교 탭 열기

### 탭 관리
- `MainWindow`가 `QTabWidget`으로 여러 비교 세션 관리
- 탭 닫기 버튼으로 개별 탭 제거 (마지막 탭은 제거 불가)

## 코딩 규칙
- UI와 핵심 로직을 `ui/`와 `core/`로 분리 유지
- PyQt6 시그널/슬롯 패턴 사용
- 다크 테마 기준 색상: 배경 `#1e1e1e`, 텍스트 `#d4d4d4`
- diff 색상: 삽입 초록(`#1a3d1a`), 삭제 빨강(`#3d1a1a`), 변경 노랑(`#3d3010`)

## 개발 브랜치
`claude/beyond-compare-research-FzmSY`
