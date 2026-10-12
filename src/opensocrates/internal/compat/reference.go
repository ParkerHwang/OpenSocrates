package compat

import (
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"strings"
)

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
			parts = append(parts, intro+"\n\n"+strings.Join(a.Guardrails, "\n\n"))
		}
		message := strings.Join(parts, "\n\n")
		if estimated(message) < 2500 {
			return message, nil
		}
	}
	return "", failure(diagnostics.Verification)
}
func (a Artifact) GroundingRepairMessage(missingRead, missingFooter bool) string {
	p, _ := contracts.CanonicalCompact(a.Path)
	missing := []string{}
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
