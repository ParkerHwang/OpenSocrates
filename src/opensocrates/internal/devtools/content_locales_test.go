package devtools

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
)

func TestReleasedTenLocaleReferenceParity(t *testing.T) {
	root := generatorRepository(t)
	projections, err := ReadObject(filepath.Join(root, "content/compiled-reasoning-content.bundle.json"))
	if err != nil {
		t.Fatal(err)
	}
	if len(arr(projections["injectable_content"])) != 48*len(releasedLocales) {
		t.Fatal("released ten-locale projection coverage changed")
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
		{"Use 2.", "ใช้ 2 และ ๓", false},
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

func TestLegacyAcceptanceCoverageRemainsVersioned(t *testing.T) {
	for _, scenario := range []struct {
		version         string
		count, revision int
	}{{"1.5.0", 2, 3}, {"1.5.1", 4, 4}, {"1.5.2", 10, 5}, {"future", 0, 0}} {
		locales, revision := acceptanceLegacyFixtureIdentity(scenario.version)
		if len(locales) != scenario.count || revision != scenario.revision {
			t.Errorf("legacy coverage changed for %s", scenario.version)
		}
	}
}

func TestReleasedProcedureLocaleBudgetsRetainOriginalAndExpandedBounds(t *testing.T) {
	procedure := "## Purpose\n\n## Use when\n\n## Do not use when\n\n## Inputs to establish\n\n## Procedure\n1. establish\n2. investigate\n3. compare\n4. evaluate\n5. conclude\n\n## Public output contract\n\n## Evidence and uncertainty rules\n\n## Stop conditions\n\n## Complement handoff\n"
	words := len(strings.Fields(procedure))
	expanded := procedure + strings.Repeat("authored ", 1000-words) + "\n"
	for _, locale := range []string{"en", "ko"} {
		if validateProcedureLocale(expanded, locale) == nil {
			t.Errorf("original %s word ceiling changed", locale)
		}
	}
	for _, locale := range []string{"fr", "de", "it", "es", "pt"} {
		if err := validateProcedureLocale(expanded, locale); err != nil {
			t.Errorf("faithful %s expansion rejected: %v", locale, err)
		}
		tooLong := procedure + strings.Repeat("authored ", 1201-words) + "\n"
		if validateProcedureLocale(tooLong, locale) == nil {
			t.Errorf("%s finite word ceiling not enforced", locale)
		}
	}
	// Script prose has one whitespace run but is measured in nonspace scalars.
	native := procedure + strings.Repeat("ก", 1000) + "\n"
	for _, locale := range []string{"zh", "ja", "th"} {
		if err := validateProcedureLocale(native, locale); err != nil {
			t.Errorf("%s char budget treated as word count: %v", locale, err)
		}
		if validateProcedureLocale(procedure+strings.Repeat("ก", 6001), locale) == nil {
			t.Errorf("%s finite character ceiling not enforced", locale)
		}
	}
	if validateProcedureLocale(expanded, "fr-FR") == nil {
		t.Fatal("unreleased procedure locale accepted")
	}
}
