package contracts_test

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"testing"
)

func TestUserSettingsSchemaAdmitsReleasedLocalesAndNullOnly(t *testing.T) {
	for _, locale := range []any{"en", "ko", "zh", "ja", nil} {
		s := domain.DefaultSettings()
		s.Value["locale_preference"] = locale
		if e := contracts.Validate("user-settings", s.Value); e != nil {
			t.Fatal(locale, e)
		}
	}
	for _, locale := range []any{"follow", "zh-CN", "ja-JP", "", true, contracts.Number(1)} {
		s := domain.DefaultSettings()
		s.Value["locale_preference"] = locale
		if e := contracts.Validate("user-settings", s.Value); e == nil {
			t.Fatal("invalid locale accepted", locale)
		}
	}
}
