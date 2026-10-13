package devtools

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

var publicIdentifier = regexp.MustCompile("`([A-Za-z][A-Za-z0-9_-]*)`")
var numericData = regexp.MustCompile(`\p{Nd}+(?:\.\p{Nd}+)?`)
var proseWord = regexp.MustCompile(`\b\w+\b`)
var englishNumbers = map[string]string{"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}

func exactReleasedLocales(v any) bool {
	m := obj(v)
	if len(m) != len(releasedLocales) {
		return false
	}
	for _, locale := range releasedLocales {
		if strings.TrimSpace(str(m[locale])) == "" {
			return false
		}
	}
	return true
}

// validateReleasedLocaleSources ports the released v1.5.2 locale contracts.
// It preserves public identifiers and numeric/routing case data without claiming
// that structural checks constitute a semantic translation review.
func validateReleasedLocaleSources(root string, catalog, teachers map[string]any) error {
	for _, raw := range arr(catalog["families"]) {
		family := obj(raw)
		for _, field := range []string{"display_name", "intent", "family_output"} {
			if !exactReleasedLocales(family[field]) {
				return fmt.Errorf("catalog family locales invalid: %s", field)
			}
		}
	}
	teacherMethods := obj(teachers["methods"])
	if len(teacherMethods) != 48 {
		return fmt.Errorf("teacher method coverage invalid")
	}
	seenQuestions := map[string]map[string]bool{}
	for _, locale := range releasedLocales {
		seenQuestions[locale] = map[string]bool{}
	}
	methods := arr(catalog["methods"])
	if len(methods) != 48 {
		return fmt.Errorf("catalog method coverage invalid")
	}
	for _, raw := range methods {
		method := obj(raw)
		id := str(method["id"])
		if id == "" || strings.ContainsAny(id, "/\\.") {
			return fmt.Errorf("unsafe catalog method")
		}
		dir := filepath.Join(root, "content/methods", id)
		metadata, err := ReadObject(filepath.Join(dir, "method.yaml"))
		if err != nil {
			return err
		}
		if !schemaEqual(method["display_name"], metadata["display_name"]) {
			return fmt.Errorf("catalog method name mismatch: %s", id)
		}
		for _, field := range []string{"display_name", "route_when", "avoid_when", "required_public_output"} {
			if !exactReleasedLocales(method[field]) {
				return fmt.Errorf("catalog method locales invalid: %s.%s", id, field)
			}
		}
		english, err := os.ReadFile(filepath.Join(dir, "procedure.en.md"))
		if err != nil {
			return err
		}
		sourceCases, err := ReadObject(filepath.Join(dir, "cases.en.yaml"))
		if err != nil {
			return err
		}
		localized := obj(teacherMethods[id])
		if len(localized) != len(releasedLocales) {
			return fmt.Errorf("teacher locale coverage invalid: %s", id)
		}
		for _, locale := range releasedLocales {
			questions := arr(localized[locale])
			if len(questions) != 3 {
				return fmt.Errorf("teacher count invalid: %s.%s", id, locale)
			}
			for _, raw := range questions {
				question := str(raw)
				if !strings.HasSuffix(question, "?") || len([]rune(question)) < 20 || len([]rune(question)) > 220 || strings.ContainsAny(question, "\n\x00") || seenQuestions[locale][question] {
					return fmt.Errorf("teacher contract invalid: %s.%s", id, locale)
				}
				seenQuestions[locale][question] = true
			}
			if locale == "en" || locale == "ko" {
				continue
			}
			translated, err := os.ReadFile(filepath.Join(dir, "procedure."+locale+".md"))
			if err != nil {
				return err
			}
			if string(translated) == string(english) {
				return fmt.Errorf("untranslated procedure: %s.%s", id, locale)
			}
			identifiers := map[string]bool{}
			for _, match := range publicIdentifier.FindAllStringSubmatch(string(translated), -1) {
				identifiers[match[1]] = true
			}
			for _, match := range publicIdentifier.FindAllStringSubmatch(string(english), -1) {
				if !identifiers[match[1]] {
					return fmt.Errorf("translated public identifier missing: %s.%s", id, locale)
				}
			}
			targetCases, err := ReadObject(filepath.Join(dir, "cases."+locale+".yaml"))
			if err != nil {
				return err
			}
			if targetCases["schema"] != sourceCases["schema"] || len(arr(targetCases["cases"])) != len(arr(sourceCases["cases"])) {
				return fmt.Errorf("translated cases coverage invalid: %s.%s", id, locale)
			}
			for i, sourceRaw := range arr(sourceCases["cases"]) {
				source, target := obj(sourceRaw), obj(arr(targetCases["cases"])[i])
				if len(source) != len(target) {
					return fmt.Errorf("translated case fields invalid: %s.%s", id, locale)
				}
				for field, value := range source {
					if _, ok := target[field]; !ok {
						return fmt.Errorf("translated case field missing: %s.%s.%s", id, locale, field)
					}
					if field != "prompt" && field != "rationale" {
						if !schemaEqual(value, target[field]) {
							return fmt.Errorf("translated case routing changed: %s.%s.%s", id, locale, field)
						}
						continue
					}
					if !translatedNumbersPreserved(str(value), str(target[field])) {
						return fmt.Errorf("translated case numeric data changed: %s.%s.%s", id, locale, field)
					}
				}
			}
		}
	}
	for _, locale := range releasedLocales {
		if len(seenQuestions[locale]) != 144 {
			return fmt.Errorf("teacher uniqueness invalid: %s", locale)
		}
	}
	return nil
}

func translatedNumbersPreserved(source, target string) bool {
	if strings.TrimSpace(target) == "" || target == source {
		return false
	}
	counts := func(text string) map[string]int {
		m := map[string]int{}
		for _, number := range numericData.FindAllString(text, -1) {
			m[number]++
		}
		return m
	}
	from, to := counts(source), counts(target)
	allowed := map[string]int{}
	for n, count := range from {
		allowed[n] = count
		if to[n] < count {
			return false
		}
	}
	for _, word := range proseWord.FindAllString(strings.ToLower(source), -1) {
		if number := englishNumbers[word]; number != "" {
			allowed[number]++
		}
	}
	for number, count := range to {
		if count > allowed[number] {
			return false
		}
	}
	return true
}
