# AGENTS.md

## 현재 목표

- 기존 모델 포맷(.obj, .glb)에서 vertex attribute만 지원하는 한계에서 벗어나 edge, face 등 다른 도메인의 attribute도 저장되는 포맷(Topolyx) 만들기
- Topolyx의 import와 export를 지원하는 blender extension 만들기

## 참고 문서
- 프로젝트 내부
    - `docs/`
        - `overview.md`: Extension 전체 구조 및 설계
        - `architecture.md`: 파일별 api 시그니처 및 역할
        - `TESTING.md`: 테스트 실행 방법
- 프로젝트 외부
    - `sources/topolyx/`
      - `SPECIFICATION.md`: 포맷 명세
      - `CHANGELOG.md`: 포맷 변경사항 정리
    - `sources/blender_addon_docs/`: 블렌더 문서의 애드온 부분 발췌
    - `sources/blender_mesh_store/`: 블렌더 문서의 메쉬 저장 방식 부분 발췌
    - `sources/blender_python_reference_5_1/`: 블렌더 문서의 파이썬 레퍼런스 부분 발췌

## 주의사항

- 모호한 점이 있으면 혼자 추측해서 결정하지 말고 사용자에게 물어보기
- 반드시 프로젝트 내부 문서와 포맷 명세 문서는 참고할 것

- 한국어로 코딩 주석과 설명을 작성할 때, 유니코드 토큰 깨짐이나 글자 바꿈 현상이 발생하지 않도록 각 문장을 명확한 완성형 한글 UTF-8 텍스트로 결합하여 출력할 것

- blender extension 개발 중 blender에서 백그라운드 테스트를 돌릴 때 발생활 수 있는 RuntimeError 중 하나는 이미 `~/.config/blender/5.1/extensions/user_default/`에 이미 설치된 애드온과의 충돌로 인한 것일 수 있으며, 참고할 것

- blender extension 개발 중 `blender -b -P topolyx_import_export/tests/run_all.py` 명령어로 테스트가 실행되지 않으면, `/home/ymh/.local/bin/blender -b -P topolyx_import_export/tests/run_all.py` 명령어로 다시 시도해 볼 것
- 