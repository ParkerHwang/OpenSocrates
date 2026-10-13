package domain

import "testing"

func TestReleasedLocaleScriptDetectionAndPrecedence(t *testing.T) {
	for _, test := range []struct {
		text   string
		digits bool
		want   string
	}{
		{"", true, "en"}, {"🙂 العربية", true, "en"}, {"한a", true, "en"}, {"한字", true, "en"},
		{"한글a字", true, "ko"}, {"中文a한", true, "zh"}, {"中文", true, "zh"},
		{"한국어中文ABCあ", true, "ja"}, {"한국어中文ABCカ", true, "ja"}, {"한국어中文ABCｶ", true, "ja"},
		{"한12", true, "en"}, {"한12", false, "ko"}, {"中12", true, "en"}, {"中12", false, "zh"},
		{"㐀", true, "zh"}, {"𠀀", true, "zh"}, {"゗", true, "en"}, {"・", true, "en"}, {"ﾞ", true, "en"},
	} {
		if got := DetectLocale(test.text, test.digits); got != test.want {
			t.Fatalf("%q digits=%v: got %s want %s", test.text, test.digits, got, test.want)
		}
	}
	en, ko, zh, ja, invalid := "en", "ko", "zh", "ja", "zh-CN"
	for _, test := range []struct {
		explicit, stored *string
		want             string
	}{
		{&en, &ko, "en"}, {nil, &ko, "ko"}, {&zh, &ja, "zh"}, {&ja, &invalid, "ja"},
		{&invalid, &ja, ""}, {nil, &invalid, ""}, {nil, nil, "ja"},
	} {
		if got := ResolveLocale(test.explicit, test.stored, "あ", true); got != test.want {
			t.Fatalf("preference result %q want %q", got, test.want)
		}
	}
	for _, invalid := range []string{"", "follow", "JA", "zh-CN", "jp", "fr"} {
		if SupportedLocale(invalid) {
			t.Fatalf("alias accepted: %q", invalid)
		}
	}
}
