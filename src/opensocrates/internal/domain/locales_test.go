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
		{"กข", true, "th"}, {"ก한", true, "en"}, {"ก中", true, "en"}, {"กa", true, "en"},
		{"กขa한中", true, "th"}, {"한글ก中a", true, "ko"}, {"中文ก한a", true, "zh"},
		{"กขあ", true, "ja"}, {"กขｶ", true, "ja"},
		{"ก12", true, "en"}, {"ก12", false, "th"},
		{"\u0E00", true, "en"}, {"\u0E01", true, "th"}, {"\u0E3A", true, "th"},
		{"\u0E3B\u0E3F", true, "en"}, {"\u0E40", true, "th"}, {"\u0E4E", true, "th"}, {"\u0E4F\u0E50", true, "en"},
		{"Bonjour français", true, "en"}, {"Deutsch", true, "en"}, {"Italiano", true, "en"}, {"Español", true, "en"}, {"Português", true, "en"},
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
	for _, invalid := range []string{"", "follow", "JA", "zh-CN", "jp", "fr-FR", "pt-BR", "th-TH", "ru"} {
		if SupportedLocale(invalid) {
			t.Fatalf("alias accepted: %q", invalid)
		}
	}
}

func TestTenReleasedLocalePreferencesOverrideScripts(t *testing.T) {
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
		if !SupportedLocale(locale) {
			t.Fatal("released choice rejected", locale)
		}
		if got := ResolveLocale(nil, &locale, "あก한中", true); got != locale {
			t.Fatal("stored choice lost", locale, got)
		}
		stored := "ja"
		if got := ResolveLocale(&locale, &stored, "あก한中", false); got != locale {
			t.Fatal("explicit choice lost", locale, got)
		}
	}
}
