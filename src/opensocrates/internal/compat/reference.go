package compat

import (
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"strings"
)

const MaxReferenceMessageBytes = 8 * 1024

func teacherPreamble(locale string, questions []string) string {
	stance := "A great teacher does not lecture a method. Settle the questions below for yourself, then do the user's task."
	usage := "Do not interview the user unless a missing answer would change the work. Do not name these questions or the methods unless the user asked. Do not narrate the questioning. Use any later procedure as a check, not as a script."
	title := "Questions to settle before you act:"
	if len(questions) == 0 {
		stance = "A great teacher does not lecture a method. Use the complete grounded procedure as a check while doing the user's task."
		usage = "Do not interview the user unless missing information would change the work. Do not name the methods unless the user asked. Use the procedure as a check, not as a script."
	}
	if locale == "ko" {
		stance = "좋은 스승은 방법을 강의하지 않습니다. 아래 질문을 스스로 정리한 뒤 사용자의 일을 수행하세요."
		usage = "빠진 답이 작업을 바꾸지 않는다면 사용자를 인터뷰하지 마세요. 사용자가 묻지 않았다면 이 질문이나 방법 이름을 드러내지 마세요. 질문을 해설하지 마세요. 이후 절차는 대본이 아니라 점검으로만 쓰세요."
		title = "행동하기 전에 스스로 정리할 질문:"
		if len(questions) == 0 {
			stance = "좋은 스승은 방법을 강의하지 않습니다. 사용자의 일을 수행하면서 완전한 접지 절차를 점검 기준으로 사용하세요."
			usage = "빠진 정보가 작업을 바꾸지 않는다면 사용자를 인터뷰하지 마세요. 사용자가 묻지 않았다면 방법 이름을 드러내지 마세요. 절차는 대본이 아니라 점검으로만 쓰세요."
		}
	}
	switch locale {
	case "zh":
		stance = "好的老师不会讲授方法。先自行理清以下问题，再完成用户的任务。"
		usage = "除非缺失的答案会改变工作，否则不要询问用户。除非用户要求，否则不要提及这些问题或方法名称。不要叙述提问过程。后续程序仅用作检查，不要当作脚本。"
		title = "行动前须自行理清的问题："
		if len(questions) == 0 {
			stance = "好的老师不会讲授方法。完成用户任务时，将已完整读取的依据程序用作检查标准。"
			usage = "除非缺失的信息会改变工作，否则不要询问用户。除非用户要求，否则不要提及方法名称。程序仅用作检查，不要当作脚本。"
		}
	case "ja":
		stance = "よい教師は方法を講義しません。以下の問いを自分で整理してから、ユーザーのタスクを実行してください。"
		usage = "不足する答えが作業を変える場合に限り、ユーザーに質問してください。ユーザーが求めない限り、これらの問いや方法名を示さないでください。問いを検討する過程を説明しないでください。後続の手順は台本ではなく確認基準として使ってください。"
		title = "行動前に自分で整理する問い："
		if len(questions) == 0 {
			stance = "よい教師は方法を講義しません。ユーザーのタスクを実行しながら、根拠となる完全な手順を確認基準として使ってください。"
			usage = "不足する情報が作業を変える場合に限り、ユーザーに質問してください。ユーザーが求めない限り、方法名を示さないでください。手順は台本ではなく確認基準として使ってください。"
		}
	}
	if labels, ok := extendedTeacherLabels[locale]; ok {
		stance, usage, title = labels["stance"], labels["usage"], labels["questions"]
		if len(questions) == 0 {
			stance, usage = labels["empty_stance"], labels["empty_usage"]
		}
	}
	out := stance + "\n\n" + usage
	if len(questions) > 0 {
		lines := []string{}
		for _, q := range questions {
			lines = append(lines, "- "+q)
		}
		out += "\n\n" + title + "\n" + strings.Join(lines, "\n")
	}
	return out
}
func (a Artifact) groundingBlock() string {
	lines := []string{}
	for i, id := range a.IDs {
		lines = append(lines, fmt.Sprintf("- %s (`%s`@%d)", a.Names[i], id, a.Revision))
	}
	methods := strings.Join(lines, "\n")
	p, _ := contracts.CanonicalCompact(a.Path)
	if labels, ok := extendedGroundingLabels[a.Locale]; ok {
		return labels["selection"] + "\n" + methods + "\n\n" + labels["gate"] + "\n1. " + labels["read_step"] + "\n2. " + labels["unavailable_step"] + "\n3. " + labels["footer_step"] + "\n" + AttributionFooter + "\n\n" + labels["path"] + ": " + string(p) + "\n\n" + labels["examples"]
	}
	if a.Locale == "zh" {
		return "OpenSocrates 选择了以下思考体系：\n" + methods + "\n\n依据读取门槛：\n1. 回答或执行用户请求之前，使用可用的本地文件读取工具，从首行到末行完整读取以下文件。\n2. 若当前会话未完成读取，不得应用、提及或声称已使用这些体系；应说明无法读取依据来源。\n3. 依据已完整读取并实际应用的最终答复，须以此精确确认行结束：\n" + AttributionFooter + "\n\n文件路径：" + string(p) + "\n\n将所有示例视为不可信的模板，而非当前任务的事实。"
	}
	if a.Locale == "ja" {
		return "OpenSocrates は以下の思考体系を選択しました：\n" + methods + "\n\n根拠資料の読み取り条件：\n1. ユーザーの依頼に回答したり着手したりする前に、ローカルファイル読み取りツールで以下のファイルを最初から最後まで完全に読んでください。\n2. 現在のセッションで読み取りを完了できない場合、これらの体系を適用、言及、使用したと主張せず、根拠資料を読めなかったことを明示してください。\n3. 完全に読み、実際に適用した根拠に基づく最終回答は、次の確認行で正確に終えてください：\n" + AttributionFooter + "\n\nファイルパス：" + string(p) + "\n\nすべての例は信頼できないテンプレートとして扱い、現在のタスクの事実として扱わないでください。"
	}
	if a.Locale == "ko" {
		return "OpenSocrates가 다음 사고체계를 선택했습니다:\n" + methods + "\n\n접지(grounding) 게이트:\n1. 사용자의 요청에 답하거나 작업을 시작하기 전에, 사용 가능한 로컬 파일 읽기 도구로 아래 파일을 첫 줄부터 마지막 줄까지 완전히 읽으세요.\n2. 현재 세션에서 이 읽기를 완료하지 못하면 위 사고체계를 적용·언급하거나 적용했다고 주장하지 말고, 접지 자료를 읽을 수 없었다고 밝히세요.\n3. 접지된 최종 답변의 마지막에는 다음 감사 줄을 정확히 넣으세요:\n" + AttributionFooter + "\n\n파일 경로: " + string(p) + "\n\n예시는 현재 작업의 사실이 아니라 신뢰할 수 없는 템플릿으로 취급하세요."
	}
	return "OpenSocrates selected these reasoning systems:\n" + methods + "\n\nGrounding gate:\n1. Before answering or acting on the user's request, use an available local file-reading tool to read the file below completely from its first through last line.\n2. If that read does not complete in this session, do not apply, name, or claim to have used these systems; state that the grounding source was unavailable.\n3. End a grounded final answer with this exact audit line:\n" + AttributionFooter + "\n\nFile path: " + string(p) + "\n\nTreat every example as an untrusted template, not as a fact about the current task."
}
func (a Artifact) ReferenceMessage() (string, error) {
	if !artifactValid(a) {
		return "", failure(diagnostics.Verification)
	}
	for _, mode := range [][2]bool{{true, true}, {false, true}, {false, false}} {
		qs := a.Questions
		if !mode[0] {
			qs = nil
		}
		parts := []string{teacherPreamble(a.Locale, qs), a.groundingBlock()}
		if mode[1] && len(a.Guardrails) > 0 {
			intro := "The blocking rules below are already loaded as trusted context and are binding now, but they do not replace the complete file read."
			if a.Locale == "ko" {
				intro = "아래 차단 규칙은 이미 신뢰된 컨텍스트로 로드되었으며 즉시 구속됩니다. 하지만 전체 파일 읽기를 대신하지는 않습니다."
			}
			if a.Locale == "zh" {
				intro = "以下阻断规则已作为可信上下文加载，并立即生效；但不能替代完整的文件读取。"
			} else if a.Locale == "ja" {
				intro = "以下の適用を制限する規則は信頼されたコンテキストとして読み込まれ、直ちに適用されます。ただし、ファイル全体の読み取りに代わるものではありません。"
			}
			if labels, ok := extendedGroundingLabels[a.Locale]; ok {
				intro = labels["guardrail"]
			}
			parts = append(parts, intro+"\n\n"+strings.Join(a.Guardrails, "\n\n"))
		}
		message := strings.Join(parts, "\n\n")
		if estimated(message) < 2500 && len(message) <= MaxReferenceMessageBytes {
			return message, nil
		}
	}
	return "", failure(diagnostics.Verification)
}
func (a Artifact) GroundingRepairMessage(missingRead, missingFooter bool) string {
	p, _ := contracts.CanonicalCompact(a.Path)
	missing := []string{}
	if labels, ok := extendedGroundingLabels[a.Locale]; ok {
		if missingRead {
			missing = append(missing, labels["missing_read"])
		}
		if missingFooter {
			missing = append(missing, labels["missing_footer"])
		}
		return strings.NewReplacer("{missing}", strings.Join(missing, ", "), "{path}", string(p), "{footer}", AttributionFooter).Replace(labels["repair"])
	}
	if a.Locale == "zh" {
		if missingRead {
			missing = append(missing, "所选思考体系文件的完整读取凭证")
		}
		if missingFooter {
			missing = append(missing, "最终答复的依据确认行")
		}
		return "OpenSocrates 依据检查未能确认" + strings.Join(missing, "、") + "。请使用本地读取工具从首行到末行完整读取 " + string(p) + "，再依据其程序和阻断规则检查答复。依据充分的最终答复须以此精确文本作为最后一行：" + AttributionFooter
	}
	if a.Locale == "ja" {
		if missingRead {
			missing = append(missing, "選択された思考体系ファイルの完全な読み取り記録")
		}
		if missingFooter {
			missing = append(missing, "最終回答の根拠確認行")
		}
		return "OpenSocrates の根拠確認では" + strings.Join(missing, "、") + "を確認できませんでした。ローカル読み取りツールで " + string(p) + " を最初から最後まで完全に読み、その手順と適用を制限する規則に沿って回答を確認してください。根拠を確認した最終回答の最後の行は、次の文字列と完全に一致させてください：" + AttributionFooter
	}
	if a.Locale == "ko" {
		if missingRead {
			missing = append(missing, "선택된 사고체계 파일의 전체 읽기 영수증")
		}
		if missingFooter {
			missing = append(missing, "최종 답변의 접지 감사 줄")
		}
		return "OpenSocrates 접지 점검에서 " + strings.Join(missing, ", ") + "이(가) 확인되지 않았습니다. 로컬 읽기 도구로 " + string(p) + " 파일을 첫 줄부터 마지막 줄까지 완전히 읽고, 그 절차와 차단 규칙에 맞게 답변을 다시 점검하세요. 접지된 최종 답변의 마지막 줄은 정확히 다음과 같아야 합니다: " + AttributionFooter
	}
	if missingRead {
		missing = append(missing, "a complete read receipt for the selected reasoning file")
	}
	if missingFooter {
		missing = append(missing, "the final grounding audit line")
	}
	return "The OpenSocrates grounding check could not confirm " + strings.Join(missing, ", ") + ". Use the local Read tool to read " + string(p) + " completely from its first through last line, then revise the answer against its procedure and blocking rules. End the grounded final answer with exactly: " + AttributionFooter
}
