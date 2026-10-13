package devtools

import (
	"strings"
	"testing"
)

func TestPublicationChildEnvironmentIsolatesSigningSecretsAndRetainsPublicationAuth(t *testing.T) {
	private := []string{"OPENSOCRATES_MAC_CERTIFICATE_P12_BASE64", "OPENSOCRATES_MAC_CERTIFICATE_PASSWORD", "OPENSOCRATES_NOTARY_APPLE_ID", "OPENSOCRATES_NOTARY_APP_PASSWORD"}
	for _, name := range private {
		t.Setenv(name, "synthetic-signing-secret")
	}
	t.Setenv("GH_TOKEN", "synthetic-publication-auth")
	t.Setenv("OPENSOCRATES_MAC_TEAM_ID", "6HM2UD6746")
	child := map[string]string{}
	for _, item := range publicationChildEnvironment() {
		name, value, _ := strings.Cut(item, "=")
		child[name] = value
	}
	for _, name := range private {
		if _, found := child[name]; found {
			t.Fatal("source inspection inherited a signing credential")
		}
	}
	if child["GH_TOKEN"] != "synthetic-publication-auth" || child["OPENSOCRATES_MAC_TEAM_ID"] != "6HM2UD6746" {
		t.Fatal("credential isolation removed required publication authentication or public configuration")
	}
}
