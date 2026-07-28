# PTMGenerator2 버전 관리

## 개요

버전 정보는 `version.py` 한 곳에서만 관리하고, `scripts/bump_version.py`로 올립니다.
명령 체계는 Modan2의 `manage_version.py`, CTHarvester의 `scripts/bump_version.py`와
동일하게 맞췄습니다.

## 핵심 원칙

- **Single Source of Truth**: `version.py`의 `__version__`이 유일한 버전 정보입니다.
- **Semantic Versioning**: [SemVer 2.0.0](https://semver.org/)을 따릅니다.
- **자동화**: 버전 변경 · CHANGELOG 갱신 · 커밋 · 태그를 한 번에 처리합니다.

## 관련 파일

| 파일 | 역할 |
|---|---|
| `version.py` | 버전 정보. **여기만 고칩니다** |
| `scripts/bump_version.py` | 버전 갱신 자동화 |
| `CHANGELOG.md` | 버전별 변경 사항 ([Keep a Changelog](https://keepachangelog.com/) 형식) |
| `pyproject.toml` | `dynamic = ["version"]`으로 `version.py`에서 읽어옴 |
| `PTMGenerator2.spec` | Windows 파일 속성에 넣을 버전을 `version.py`에서 읽음 |
| `installer/PTMGenerator2.iss.template` | 설치 파일 이름과 프로그램 추가/제거 항목의 버전. CI가 `version.py`에서 채워 넣음 |
| `.github/workflows/release.yml` | 태그와 `version.py`가 다르면 릴리스를 거부 |

`tests/test_version_consistency.py`가 이 연결이 끊기지 않았는지 검사합니다.

## 명령어

### 정식 버전 올리기

| 명령 | 예 |
|---|---|
| `major` | `1.2.3` → `2.0.0` |
| `minor` | `1.2.3` → `1.3.0` |
| `patch` | `1.2.3` → `1.2.4` |

```bash
python scripts/bump_version.py patch
```

### Pre-release 시작

토큰(`alpha`·`beta`·`rc`)을 생략하면 `alpha`입니다.

```bash
python scripts/bump_version.py preminor        # 0.2.0 -> 0.3.0-alpha.1
python scripts/bump_version.py preminor beta   # 0.2.0 -> 0.3.0-beta.1
```

### Pre-release 번호 올리기 / 단계 전환 / 정식 전환

```bash
python scripts/bump_version.py prerelease   # 0.2.0-beta.1 -> 0.2.0-beta.2
python scripts/bump_version.py stage rc     # 0.2.0-beta.3 -> 0.2.0-rc.1
python scripts/bump_version.py release      # 0.2.0-rc.1   -> 0.2.0
```

### 명시적 지정

```bash
python scripts/bump_version.py --set 1.0.0
```

## 릴리스 절차

1. **변경 사항을 `CHANGELOG.md`의 `## [Unreleased]`에 적습니다.**
   스크립트는 이 섹션을 릴리스 항목으로 바꾸고 빈 `Unreleased`를 새로 엽니다.
   섹션이 없으면 거부합니다.

2. **실행파일에 영향을 주는 변경이 있었다면 먼저 빌드를 돌려봅니다.**
   ```bash
   gh workflow run build.yml
   ```
   릴리스 도중에 빌드가 깨지면 태그는 이미 푸시된 상태로 남습니다. Windows에서만
   드러나는 실패가 실제로 있었습니다 (devlog 007).

3. **워킹트리를 깨끗하게 만듭니다.** 커밋되지 않은 변경이 있으면 거부합니다.

4. **버전을 올립니다.**
   ```bash
   python scripts/bump_version.py patch --dry-run   # 먼저 확인
   python scripts/bump_version.py patch
   ```
   `version.py`와 `CHANGELOG.md`가 갱신되고, `chore: release v<버전>` 커밋과
   `v<버전>` 주석 태그가 만들어집니다. 태그 메시지에는 해당 CHANGELOG 항목이 들어갑니다.

5. **푸시합니다.**
   ```bash
   git push && git push origin v0.1.3
   ```
   `--push`를 주면 4번에서 함께 처리합니다.

6. **`release.yml`이 이어받습니다.** 태그와 `version.py`가 일치하는지 검사하고,
   전체 테스트 매트릭스를 돌린 뒤, PyInstaller 빌드 → `--self-test` → Inno Setup
   순으로 `PTMGenerator2_v<버전>_build<번호>_Installer.exe` 를 만들어 GitHub
   Release에 올립니다. 릴리스 노트는 `CHANGELOG.md`에서 가져옵니다.

## 주의

- **`version.py`를 손으로 고치지 마세요.** CHANGELOG와 태그가 어긋납니다.
- **태그를 손으로 만들지 마세요.** `release.yml`의 검증 단계에서 막힙니다.
  이 검사는 "v0.2.4로 태그했는데 `version.py`를 안 올림" 실수를 잡기 위한 것입니다.
- 되돌리려면 태그와 커밋을 함께 지워야 합니다:
  ```bash
  git tag -d v0.1.3
  git reset --hard HEAD~1
  ```
  이미 푸시했다면 GitHub의 릴리스와 원격 태그도 지워야 합니다.
