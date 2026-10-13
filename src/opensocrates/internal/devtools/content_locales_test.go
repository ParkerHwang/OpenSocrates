package devtools

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
)

func TestReleasedFourLocaleReferenceParity(t *testing.T) {
	root := generatorRepository(t)
	projections, err := ReadObject(filepath.Join(root, "content/compiled-reasoning-content.bundle.json"))
	if err != nil {
		t.Fatal(err)
	}
	if len(arr(projections["injectable_content"])) != 192 {
		t.Fatal("released four-locale projection coverage changed")
	}
	fixed, err := content.Load()
	if err != nil {
		t.Fatal(err)
	}
	for _, method := range fixed.Methods {
		for _, locale := range releasedLocales {
			actual, err := assembleReference(projections, method.ID, locale)
			if err != nil {
				t.Fatal(err)
			}
			expected, err := fixed.Assemble([]string{method.ID}, locale)
			if err != nil || actual != expected {
				t.Errorf("reference differs from canonical runtime: %s.%s: %v", method.ID, locale, err)
			}
		}
	}
}

func TestTranslatedNumbersPreserveExplicitDataAndBoundEnglishWords(t *testing.T) {
	for _, tc := range []struct {
		source, target string
		want           bool
	}{
		{"Compare two teams with 10.5 points and 2 points.", "比较2个团队的10.5分与2分。", true},
		{"Compare two teams with 10.5 points and 2 points.", "比較する2チームの10.6点と2点。", false},
		{"Compare two teams with 10.5 points and 2 points.", "比较3个团队的10.5分与2分。", false},
		{"Use 2 and 2.", "2を使用します。", false},
		{"Use 2.", "Use 2.", false},
	} {
		if got := translatedNumbersPreserved(tc.source, tc.target); got != tc.want {
			t.Errorf("numeric preservation = %v want %v", got, tc.want)
		}
	}
}

func TestLocaleCommandProjectionUsesNativeGrammar(t *testing.T) {
	for _, target := range []string{"darwin-arm64", "windows-x64", "windows-arm64"} {
		actual := specializeNativeCommands("`${PLUGIN_ROOT}/bin/launch.sh locale codex get`\n`${PLUGIN_ROOT}/bin/launch.sh locale codex set ja`\n`${PLUGIN_ROOT}/bin/launch.sh locale codex reset`", "codex", target)
		if strings.Contains(actual, "locale codex") || !strings.Contains(actual, "\" locale set ja") {
			t.Fatal("legacy locale grammar remains", actual)
		}
	}
}
