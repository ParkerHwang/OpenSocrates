OpenSocrates Office Evaluation Lab / 사무 업무 비교 실험실

처음 시작하기
1. Mac과 Windows 각각의 개인 폴더에 ZIP을 새로 풉니다.
2. Python 3.12 이상과 테스트할 앱을 설치하고 정상 로그인합니다.
3. Mac은 Start Lab.command, Windows는 Start Lab.cmd를 두 번 클릭합니다.
4. 열린 화면에서 앱 하나와 절차 확인 2과제·6회를 선택합니다.
5. 준비된 자료·프롬프트로 앱에서 직접 실행하고, 최종 답변을 확인·승인합니다.
6. 답변을 모두 모은 뒤 먼저 쓸 결과를 고릅니다. 그 후에 조건을 공개합니다.
같은 실행기를 다시 열면 이어서 진행합니다. 다른 기기·새 실험은 ZIP을 새로 풉니다.
화면의 모델·기존 설정 확인은 직접 해야 하며, 이 도구는 모델을 호출하지 않습니다.
자세한 한국어 안내: guides/evaluation-lab.ko.md

English quick start
1. Unzip to a writable personal folder. / 개인 쓰기 가능한 폴더에 압축을 풉니다.
2. Install Python 3.12 or later from https://www.python.org/downloads/ if missing.
3. macOS: double-click Start Lab.command. Windows: double-click Start Lab.cmd.
4. Follow the local browser guide. Real apps are operated manually; no API calls,
   credentials, provider clients or application settings are installed by this kit.
5. Close the terminal to stop. Reopen to resume the same lab-data ledger.
   To start a separate study, use another freshly unzipped copy or --data NEW_PATH.

Details / 상세 가이드: guides/evaluation-lab.ko.md and guides/evaluation-lab.md.
Mac/Windows authenticated native-app qualification remains separate live evidence.
Work content-only transport is experimental. Claude account skill sync can affect
A/B baselines. Only actor folders should be granted to apps, never the whole kit.
Do not put private work or transcripts in the lab. Approve final synthetic outputs
before retention/export. Collection only watches the dedicated out/final.md file.
A new folder is not proof of a clean app/account or OS.

Read-only merge / 내보낸 결과 합치기:
  python merge-exports.py first.json second.json --output combined.json
This never resumes a study, extracts ZIPs, uploads results or overwrites output.
