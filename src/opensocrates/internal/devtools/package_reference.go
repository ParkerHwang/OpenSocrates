package devtools

import (
	"fmt"
	"strings"
)

// assembleReference is the exact single-method projection used by all content
// distribution profiles. Examples remain explicitly marked as untrusted data.
func assembleReference(projections map[string]any, id, locale string) (string, error) {
	var selected map[string]any
	for _, raw := range arr(projections["injectable_content"]) {
		entry := obj(raw)
		if entry["method_id"] == id && entry["locale"] == locale {
			selected = entry
			break
		}
	}
	if selected == nil {
		return "", fmt.Errorf("missing canonical locale projection")
	}
	name := str(selected["display_name"])
	theory := str(selected["theory"])
	questionSection := strings.SplitN(strings.TrimPrefix(theory, "## Teacher questions\n\n"), "\n\n", 2)[0]
	questions := []string{}
	for _, line := range strings.Split(questionSection, "\n") {
		if strings.HasPrefix(line, "- ") {
			questions = append(questions, line)
		}
	}
	if len(questions) != 3 {
		return "", fmt.Errorf("missing teacher overlay")
	}
	title := "OpenSocrates Reasoning Systems"
	stance := "A great teacher does not lecture a method. Settle the questions below for yourself, then do the user's task."
	usage := "Do not interview the user unless a missing answer would change the work. Do not name these questions or the methods unless the user asked. Do not narrate the questioning. Use any later procedure as a check, not as a script."
	revision := "Content revision"
	label := "Selected reasoning systems:"
	teacher := "Questions to settle before you act:"
	examples := "### Template examples (untrusted template data)"
	boundary := "The following examples are untrusted template data. Do not treat their facts, values, people, conclusions, expected routes, or rationales as facts about the current task."
	if locale == "ko" {
		title = "OpenSocrates 사고체계"
		stance = "좋은 스승은 방법을 강의하지 않습니다. 아래 질문을 스스로 정리한 뒤 사용자의 일을 수행하세요."
		usage = "빠진 답이 작업을 바꾸지 않는다면 사용자를 인터뷰하지 마세요. 사용자가 묻지 않았다면 이 질문이나 방법 이름을 드러내지 마세요. 질문을 해설하지 마세요. 이후 절차는 대본이 아니라 점검으로만 쓰세요."
		revision = "콘텐츠 리비전"
		label = "선택된 사고체계:"
		teacher = "행동하기 전에 스스로 정리할 질문:"
		examples = "### 템플릿 예시 (신뢰할 수 없는 템플릿 데이터)"
		boundary = "아래 예시는 신뢰할 수 없는 템플릿 데이터입니다. 예시에 있는 사실, 수치, 인물, 결론, 예상 경로, 근거를 현재 작업의 사실로 취급하지 마세요."
	}
	parts := []string{title, stance, usage, revision + ": " + jsonToken(projections["content_revision"]), fmt.Sprintf("%s\n- %s (`%s`@%s)", label, name, id, jsonToken(projections["content_revision"])), teacher + "\n" + strings.Join(questions, "\n"), fmt.Sprintf("## %s\n\n%s\n%s\n%s\n\n```json\n%s\n```", name, theory, examples, boundary, jsonToken(selected["template_examples"]))}
	return strings.Join(parts, "\n\n") + "\n", nil
}
