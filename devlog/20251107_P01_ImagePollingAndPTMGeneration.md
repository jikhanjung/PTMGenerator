# PTMGenerator2 개선 계획

**작성일**: 2025-11-07
**버전**: 0.1.2
**작성자**: 개발 로그

## 개요

PTMGenerator2의 이미지 polling 방식과 PTM 생성 프로세스를 개선하여 더 정확하고 유연한 동작을 구현합니다.

## 현재 상황 분석

### 1. 이미지 Polling 동작 (`get_incoming_image()` 메서드)

**위치**: PTMGenerator2.py:390-421

**현재 동작**:
```python
# 404라인
for filepath in base_path.rglob('*'):
```

- `Path.rglob('*')`를 사용하여 **재귀적으로 하위 디렉토리까지 모두 검색**
- 지정한 디렉토리뿐만 아니라 모든 하위 폴더의 이미지까지 감지
- 카메라가 하위 폴더에 이미지를 저장하는 경우를 대비한 것으로 보임

**문제점**:
- 불필요한 하위 디렉토리 검색으로 인한 성능 저하 가능성
- 의도하지 않은 하위 폴더의 이미지를 감지할 위험
- 사용자가 지정한 디렉토리만 모니터링하길 원함

### 2. PTM 생성 프로세스 (`generatePTM()` 메서드)

**위치**: PTMGenerator2.py:686-746

**현재 동작**:
```python
# 701-711라인
for image in self.image_data:
    i, directory, image_name = image
    if image_directory is None:
        image_directory = directory
    if image_name == '-':  # 실패한 이미지만 제외
        continue
    image_count += 1
    image_name = image_name.split('.')[0] + '.' + image_name.split('.')[1].lower()
    ret_str += os.path.join( directory, image_name ) + " " + " ".join([str(f) for f in LIGHT_POSITION_LIST[i]]) + "\n"
```

**동작 방식**:
1. `self.image_data`의 모든 이미지를 순회
2. `image_name == '-'`인 경우(실패한 캡처)만 제외
3. `.lp` 파일에 이미지 경로와 조명 위치 기록
4. PTMfitter.exe를 호출하여 PTM 파일 생성

**문제점**:
- 사용자가 특정 이미지를 **선택적으로 제외**할 수 없음
- 실패한 이미지 외에는 모두 포함됨
- 품질이 좋지 않은 이미지나 재촬영 전 이미지를 제외하고 싶은 경우 대응 불가

### 3. 파일 경로 처리 검증

**현재 동작**:
```python
# 711라인
ret_str += os.path.join( directory, image_name ) + " " + ...
```

**image_data 구조**:
```python
# 487라인 (take_picture_process)
self.image_data[self.current_index] = (self.current_index, directory, filename)
```

**분석**:
- `directory`는 `os.path.split(new_image)`에서 얻어짐 (482라인)
- `new_image`는 `get_incoming_image()`에서 `str(filepath)`로 반환 (416라인)
- `filepath`는 `Path` 객체의 절대 경로
- **결론**: 이미 전체 경로로 저장되고 있음 ✓

**확인이 필요한 부분**:
- `os.path.join(directory, image_name)`의 결과가 항상 절대 경로인지 재확인
- 상대 경로가 섞여 있을 가능성 검토

## 개선 계획

### Task 1: Polling을 현재 디렉토리만 검색하도록 수정

**파일**: PTMGenerator2.py
**메서드**: `get_incoming_image()` (390-421라인)

**수정 내용**:
```python
# 변경 전 (404라인)
for filepath in base_path.rglob('*'):

# 변경 후
for filepath in base_path.glob('*'):
```

**영향 분석**:
- `rglob` → `glob` 변경으로 하위 디렉토리 검색 제거
- 메시지도 수정 필요: "in {directory} and subdirectories..." → "in {directory}..."

**예상 효과**:
- 성능 향상 (불필요한 재귀 검색 제거)
- 의도하지 않은 파일 감지 방지
- 사용자 의도에 맞는 동작

### Task 2: PTM 생성 시 이미지 선택 기능 추가

**구현 방안**: 선택된 행만 PTM에 포함

**방안 A - 테이블 체크박스 추가** (권장):
1. 테이블에 "Include" 체크박스 컬럼 추가
2. `image_data`에 포함 여부 플래그 추가: `(index, directory, filename, include_flag)`
3. `generatePTM()`에서 `include_flag == True`인 이미지만 처리
4. 기본값은 모두 체크된 상태

**장점**:
- 직관적인 UI
- 개별 이미지 선택/해제 가능
- 시각적으로 명확

**방안 B - 선택된 행만 사용**:
1. 현재 `table_view.selectionModel()`의 선택된 행만 PTM에 포함
2. 선택이 없으면 모든 이미지 포함
3. `generatePTM()`에서 `self.selected_rows` 확인

**장점**:
- 코드 수정 최소화
- 기존 선택 메커니즘 활용

**단점**:
- 다중 선택 시 헷갈릴 수 있음
- Ctrl/Shift 키 조작 필요

**권장 방안**: **방안 A (체크박스)** - 더 직관적이고 사용자 친화적

### Task 3: 파일 경로 절대 경로 보장

**검증 항목**:
1. `get_incoming_image()`에서 반환하는 경로 확인
2. `image_data`에 저장되는 경로 형식 확인
3. `generatePTM()`에서 `.lp` 파일에 기록되는 경로 확인

**수정 방안**:
```python
# generatePTM() 711라인 수정
# 변경 전
ret_str += os.path.join( directory, image_name ) + " " + ...

# 변경 후
image_path = os.path.abspath(os.path.join(directory, image_name))
ret_str += image_path + " " + ...
```

**추가 검증**:
- `.lp` 파일 생성 후 경로가 절대 경로인지 로그로 확인
- PTMfitter.exe가 상대 경로를 지원하는지 문서 확인

## 구현 순서

1. **Task 1** (간단) - Polling 범위 수정
2. **Task 3** (간단) - 절대 경로 보장 및 검증
3. **Task 2** (복잡) - 이미지 선택 기능 추가

## 테스트 계획

### Task 1 테스트:
- [ ] 지정 디렉토리에 이미지 파일 추가 → 정상 감지 확인
- [ ] 하위 디렉토리에 이미지 파일 추가 → 감지되지 않음 확인
- [ ] 로그 메시지가 올바르게 변경되었는지 확인

### Task 2 테스트:
- [ ] 모든 이미지 체크 → PTM 생성 성공
- [ ] 일부 이미지 체크 해제 → 체크된 이미지만 PTM에 포함
- [ ] 체크 상태가 CSV 로드 시 복원되는지 확인

### Task 3 테스트:
- [ ] 생성된 `.lp` 파일 내용 확인 → 모든 경로가 절대 경로인지 검증
- [ ] PTMfitter.exe 실행 성공 여부 확인
- [ ] 다양한 경로 형식으로 테스트 (공백 포함, 특수문자 등)

## 주의사항

1. **하위 호환성**: 기존에 저장된 CSV 파일과의 호환성 유지
2. **성능**: 체크박스 추가 시 대량 이미지 처리 성능 확인
3. **사용자 경험**: 기본 동작이 직관적이어야 함 (모든 이미지 포함이 기본)
4. **에러 처리**: 선택된 이미지가 없을 때 적절한 에러 메시지

## 예상 코드 변경 위치

- `get_incoming_image()`: 404라인, 391라인 (메시지)
- `generatePTM()`: 701-711라인 (이미지 필터링), 711라인 (절대 경로)
- `image_data` 구조 변경: 튜플 요소 추가 또는 dict로 변경
- `setup_ui()`: 테이블 컬럼 추가
- `load_csv_data()`, `update_csv()`: CSV 형식 업데이트
- 체크박스 이벤트 핸들러 추가

## 참고

- 현재 버전: 0.1.2
- Git 상태: Clean
- 최근 수정: Test Shot serial 연결 문제 해결
