OpenSocrates Office Evaluation Lab / 사무 업무 비교 실험실

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
