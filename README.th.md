<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="320">
</p>

# OpenSocrates

**นำวิธีคิด 48 วิธีมาใช้ในการสนทนากับ AI ของคุณ**

OpenSocrates มีขั้นตอนการคิดที่นำกลับมาใช้ได้สำหรับ **Claude, Codex และ
Antigravity** เปรียบเทียบทางเลือก ทำความเข้าใจข้อมูลที่ขัดแย้งกัน และมองแผนจากอีกมุม
เล่างานด้วยคำพูดของคุณเอง แต่ละวิธีมีคำถาม จุดตรวจสอบ และขั้นตอนให้หยิบมาใช้

[เริ่มจากแอปที่คุณใช้](#start-with-your-app) · [ดูตัวอย่าง](#see-it-in-a-task) · [สำรวจวิธีคิด](#a-method-for-the-question)

**48 วิธีคิด · คำแนะนำ 10 ภาษา · สัญญาอนุญาต MIT**

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh.md) · [日本語](README.ja.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Italiano](README.it.md) · [Español](README.es.md) · [Português](README.pt.md) · **ไทย**

## เครื่องมือคิดสำหรับงานตรงหน้า

- **เริ่มจากงานของคุณ** แต่ละวิธีมีคำถามและจุดตรวจสอบที่เขียนไว้แล้ว พร้อมใช้ซ้ำในบทสนทนาต่างๆ
- **หามุมมองที่ช่วยงาน** เลือกใช้วิธีสำหรับเปรียบเทียบทางเลือก ประเมินหลักฐาน สำรวจสมมติฐาน และวางแผนล่วงหน้า
- **ปรับให้เข้ากับงานของคุณ** อ่านขั้นตอนทุกวิธี ศึกษาตัวอย่าง และปรับเนื้อหาโอเพนซอร์สให้เหมาะกับงาน

<a id="see-it-in-a-task"></a>

## ลองใช้กับงานจริง

หลังตั้งค่าแล้ว ลองถามแบบนี้:

> เรากำลังจะซื้อเครื่องมือที่ให้บริการบนคลาวด์ แต่ตอนนี้งานต้องทำแบบออฟไลน์
> ควรซื้อ สร้างเครื่องมือเอง หรือทำด้วยมือไปก่อน?

สำหรับการตัดสินแบบนี้ [การวิเคราะห์ข้อแลกเปลี่ยน](content/methods/trade-off-analysis/procedure.th.md)
มีลำดับขั้นที่ใช้ซ้ำได้: ระบุข้อกำหนด เปรียบเทียบทางเลือกที่ทำได้ แยกข้อเท็จจริงที่รู้
ออกจากสมมติฐาน และอธิบายว่าอะไรจะเปลี่ยนคำแนะนำ วิธีนี้ให้โครงสร้างดังกล่าว
สำหรับใช้ร่วมกับคำขอที่คุณถามตามปกติ

<a id="start-with-your-app"></a>

## เริ่มจากแอปที่คุณใช้

เลือกแอปที่คุณต้องการใช้ OpenSocrates
[ดาวน์โหลด v1.5.3](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.3)

<details>
<summary><strong>Claude Chat และ Cowork</strong> — อัปโหลดสกิลแล้วเริ่มสนทนา</summary>

สำหรับ Claude บนเว็บ, Desktop Chat และ Cowork:

1. เปิด **Code execution and file creation** ใน **Settings → Capabilities** หากองค์กรดูแลบัญชีของคุณ ให้ยืนยันว่านโยบายองค์กรอนุญาตให้ใช้ Skills และเรียกใช้โค้ด
2. ดาวน์โหลด [ZIP สกิลบัญชี](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.3/opensocrates-1.5.3-claude-chat-skills.zip) และ [ไฟล์ SHA-256](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.3/opensocrates-1.5.3-claude-chat-skills.zip.sha256)
3. เปิด **Customize → Skills → + → Create skill → Upload a skill** อัปโหลด ZIP และเปิดใช้สกิล สำรองสกิล OpenSocrates เดิมก่อนแทนที่
4. เพิ่ม [คำแนะนำบัญชีหนึ่งครั้ง](docs/setup-guide.md#claude-standing-instructions) ในแต่ละบัญชี Claude ที่คุณใช้ โดยคงคำแนะนำเดิมไว้ เริ่มบทสนทนาใหม่และเล่างานที่ต้องการทำ

ZIP สกิลแบบพกพามีวิธีคิดและตัวอย่างฉบับเต็ม
[คู่มือตั้งค่าพร้อมภาพ](docs/setup-guide.md#2-claude-account-skill-enable-it-and-add-account-instructions) · [คู่มือ Skills ของ Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

</details>

<details>
<summary><strong>Claude Code</strong> — Mac Apple Silicon</summary>

คุณต้องมี [Node.js 20+](https://nodejs.org/en/download), Claude CLI และบัญชี Claude
ที่เข้าสู่ระบบแล้ว ใช้ได้กับ Claude Code ในเทอร์มินัลและ Code แบบ local ใน
Claude Desktop เรียกคำสั่งใน **Terminal**:

```sh
npx --yes opensocrates@1.5.3 install --host claude
npx --yes opensocrates@1.5.3 diagnose --host claude
```

ยืนยัน `enabled: true`, `integrity: verified` และ `registration: confirmed`
ตรวจคำขอความเชื่อถือของโปรเจกต์ที่ปรากฏ แล้วเริ่มเซสชัน local ใหม่
[คู่มือตั้งค่าพร้อมภาพ](docs/setup-guide.md#3-claude-code-check-the-local-mac-plugin)

</details>

<details>
<summary><strong>Codex</strong> — Mac Apple Silicon หรือ Windows x64</summary>

คุณต้องมี [Node.js 20+](https://nodejs.org/en/download) และ Codex รันไทม์เนทีฟ
รวมอยู่ในแพ็กเกจแล้ว เรียกคำสั่งใน **Terminal บน Mac** หรือ **PowerShell บน Windows**:

```sh
npx --yes opensocrates@1.5.3 install --host codex
npx --yes opensocrates@1.5.3 status --host codex
```

เปิด Codex แบบโต้ตอบและพิมพ์ `/hooks` ในช่องรับข้อความ ตรวจและอนุมัติข้อกำหนด
ฮุก OpenSocrates ทั้งเจ็ดรายการที่คุณเชื่อถือ แล้วเริ่มบทสนทนาใหม่
[คู่มือตั้งค่าพร้อมภาพ](docs/setup-guide.md#1-codex-review-and-approve-opensocrates-hooks)

หากต้องการอัปเดตการติดตั้ง Codex ที่มีอยู่:

```sh
npx --yes opensocrates@1.5.3 update --host codex
```

</details>

<details>
<summary><strong>Antigravity</strong> — Mac Apple Silicon หรือ Windows x64</summary>

คุณต้องมี [Node.js 20+](https://nodejs.org/en/download) เลือกเวิร์กสเปซและแทนพาธ
ในตัวอย่างด้วยพาธเต็มของโฟลเดอร์ที่มีอยู่แล้ว เรียกคำสั่งใน **Terminal บน Mac**
หรือ **PowerShell บน Windows**:

```sh
npx --yes opensocrates@1.5.3 install --host antigravity --workspace "/absolute/path/to/workspace"
```

บน Windows ใช้พาธไดรฟ์ในเครื่องที่ครอบด้วยเครื่องหมายคำพูด เช่น
`"C:\Work\Reading Workshop"` หากต้องการตั้งค่าแบบส่วนกลาง ให้ละ `--workspace`
เลือกติดตั้งแบบส่วนกลางหรือในเวิร์กสเปซสำหรับโปรเจกต์นั้น แล้วเริ่มบทสนทนาใหม่
[ตรวจสกิลและกฎ](docs/setup-guide.md#4-antigravity-check-both-the-skill-and-rule)

</details>

**ให้เอเจนต์ช่วยตั้งค่า?** ใช้ [ข้อความขอให้ตั้งค่า](docs/setup-guide.md#ask-an-agent-to-finish-setup)
หรือ [คู่มือติดตั้งปัจจุบัน](docs/agent-discovery.md) เลือกแต่ละแอปด้วยตัวเลือก
`--host` ตามชื่อแอป ค่าเริ่มต้นและ `--host all` เลือก Codex

<a id="a-method-for-the-question"></a>

## วิธีคิดที่เหมาะกับคำถาม

| งานที่คุณกำลังทำ | วิธีคิดที่ลองศึกษาได้ |
| --- | --- |
| เลือกระหว่างทางเลือกที่มีลำดับความสำคัญต่างกัน | [การวิเคราะห์ข้อแลกเปลี่ยน](content/methods/trade-off-analysis/procedure.th.md) |
| ทำความเข้าใจสิ่งที่แผนถือเป็นสมมติฐานตั้งต้น | [การทำแผนผังสมมติฐาน](content/methods/assumption-mapping/procedure.th.md) |
| ชั่งน้ำหนักหลักฐานรองรับข้ออ้าง | [การคิดเชิงวิพากษ์](content/methods/critical-thinking/procedure.th.md) |
| เตรียมรับสิ่งที่อาจผิดพลาดในแผน | [การวิเคราะห์ความล้มเหลวล่วงหน้า](content/methods/premortem-analysis/procedure.th.md) |

แต่ละวิธีมีวัตถุประสงค์ เงื่อนไขการใช้ ขั้นตอนฉบับเต็ม ตัวอย่าง และคำถามสำหรับผู้ช่วย
สำรวจเนื้อหา ทำตามขั้นตอนการคิด และนำวิธีกลับมาใช้ในงานต่างๆ

[ดูวิธีคิดทั้งหมด 48 วิธี](content/methods/)

## เนื้อหาวิธีคิดฉบับเต็มในสิบภาษา

อังกฤษ เกาหลี จีนตัวย่อ ญี่ปุ่น ฝรั่งเศส เยอรมัน อิตาลี สเปน โปรตุเกส และไทย
ทุกภาษามีขั้นตอนและตัวอย่างฉบับเต็มสำหรับทั้ง 48 วิธี

นี่คือภาษาของเนื้อหาวิธีคิดที่ผู้ช่วยของคุณอ่าน
[คู่มือภาษา](docs/v1.5.2.md) · [ตั้งค่าภาษาของคำแนะนำใน Codex](docs/settings.md)

## โอเพนซอร์สที่พร้อมให้สำรวจ

อ่านวิธีคิดและซอร์สฉบับเต็ม ปรับให้เข้ากับงาน หรือร่วมเพิ่มตัวอย่างใหม่
OpenSocrates เป็นโครงการอิสระภายใต้ [สัญญาอนุญาต MIT](LICENSE)

[รุ่นที่เผยแพร่](https://github.com/ParkerHwang/OpenSocrates/releases) · [คู่มือตั้งค่า](docs/setup-guide.md) · [ความเป็นส่วนตัวและความปลอดภัย](SECURITY.md) · [ร่วมพัฒนา](CONTRIBUTING.md) · [แจ้งปัญหา](https://github.com/ParkerHwang/OpenSocrates/issues/new/choose) · [ประวัติการเปลี่ยนแปลง](CHANGELOG.md)
