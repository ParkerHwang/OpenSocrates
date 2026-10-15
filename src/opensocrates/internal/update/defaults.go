package update

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update/trustconfig"
)

// DefaultRepository only uses the public root compiled into the binary. No
// server response, user path or environment variable can bootstrap new trust.
func DefaultRepository() Repository {
	identity, err := trustconfig.Load()
	if err != nil {
		return Repository{}
	}
	return Repository{BootstrapRoot: trustconfig.Root(), MetadataURL: identity.MetadataURL, TargetsURL: identity.TargetsURL, AllowedHosts: []string{"parkerhwang.github.io", "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}}
}

func DefaultNativeTrust() platform.NativeTrustPolicy {
	identity, err := trustconfig.Load()
	if err != nil {
		return platform.NativeTrustPolicy{}
	}
	return platform.NativeTrustPolicy{DarwinTeamID: identity.DarwinTeamID, WindowsCertificateSHA256: identity.WindowsCertificateSHA256}
}
