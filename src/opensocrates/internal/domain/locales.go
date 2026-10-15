package domain

// SupportedLocale accepts only the exact choices released in v1.5.2.
func SupportedLocale(locale string) bool {
	switch locale {
	case "en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th":
		return true
	default:
		return false
	}
}

// DetectLocale detects scripts without retaining text or interpreting embedded
// instructions. Selector callers exclude ASCII digits; general callers count them.
// Latin-script European languages require an explicit or stored choice.
func DetectLocale(text string, countDigits bool) string {
	korean, english, han, thai := 0, 0, 0, 0
	kana := false
	for _, r := range text {
		switch {
		case r >= 0x3041 && r <= 0x3096 || r >= 0x30A1 && r <= 0x30FA || r >= 0xFF66 && r <= 0xFF9D:
			kana = true
		case r >= 0x0E01 && r <= 0x0E3A || r >= 0x0E40 && r <= 0x0E4E:
			thai++
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
	if thai > english && thai > korean && thai > han {
		return "th"
	}
	if korean > english && korean > han && korean > thai {
		return "ko"
	}
	if han > english && han > korean && han > thai {
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
