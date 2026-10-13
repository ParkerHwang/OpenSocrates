package domain

// SupportedLocale accepts only the exact choices released in v1.5.1.
func SupportedLocale(locale string) bool {
	return locale == "en" || locale == "ko" || locale == "zh" || locale == "ja"
}

// DetectLocale detects scripts without retaining text or interpreting embedded
// instructions. Selector callers exclude ASCII digits; general callers count them.
func DetectLocale(text string, countDigits bool) string {
	korean, english, han := 0, 0, 0
	kana := false
	for _, r := range text {
		switch {
		case r >= 0x3041 && r <= 0x3096 || r >= 0x30A1 && r <= 0x30FA || r >= 0xFF66 && r <= 0xFF9D:
			kana = true
		case r >= 0xAC00 && r <= 0xD7A3:
			korean++
		case r >= 0x3400 && r <= 0x4DBF || r >= 0x4E00 && r <= 0x9FFF || r >= 0x20000 && r <= 0x323AF:
			han++
		case r >= 'A' && r <= 'Z' || r >= 'a' && r <= 'z' || countDigits && r >= '0' && r <= '9':
			english++
		}
	}
	if kana {
		return "ja"
	}
	if korean > english && korean > han {
		return "ko"
	}
	if han > english && han > korean {
		return "zh"
	}
	return "en"
}

// ResolveLocale prefers an explicit choice, then a stored choice, then script
// detection. An unsupported selected preference returns an empty value so a
// boundary can reject it instead of silently changing the requested language.
func ResolveLocale(explicit, preference *string, text string, countDigits bool) string {
	for _, choice := range []*string{explicit, preference} {
		if choice != nil {
			if !SupportedLocale(*choice) {
				return ""
			}
			return *choice
		}
	}
	return DetectLocale(text, countDigits)
}
