//go:build windows

package platform

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"golang.org/x/sys/windows"
	"os"
	"unsafe"
)

// Prefix layouts from wintrust.h CRYPT_PROVIDER_SGNR/CRYPT_PROVIDER_CERT.
// WinTrust owns and validates the referenced certificate chain until CLOSE.
type providerSigner struct {
	Size       uint32
	VerifyAsOf windows.Filetime
	Count      uint32
	Chain      *providerCertificate
}
type providerCertificate struct {
	Size        uint32
	Certificate *windows.CertContext
}

func verifyNativeSignature(ctx context.Context, path string, p NativeTrustPolicy) error {
	if !digestPattern.MatchString(p.WindowsCertificateSHA256) {
		return diagnostics.New(diagnostics.Unsupported, "native_trust")
	}
	f, e := openOwned(path, os.O_RDONLY, 0)
	if e != nil {
		return e
	}
	defer f.Close()
	utf, e := windows.UTF16PtrFromString(path)
	if e != nil {
		return failure()
	}
	info := windows.WinTrustFileInfo{Size: uint32(unsafe.Sizeof(windows.WinTrustFileInfo{})), FilePath: utf, File: windows.Handle(f.Fd())}
	data := windows.WinTrustData{Size: uint32(unsafe.Sizeof(windows.WinTrustData{})), UIChoice: windows.WTD_UI_NONE, RevocationChecks: windows.WTD_REVOKE_WHOLECHAIN, UnionChoice: windows.WTD_CHOICE_FILE, FileOrCatalogOrBlobOrSgnrOrCert: unsafe.Pointer(&info), StateAction: windows.WTD_STATEACTION_VERIFY, ProvFlags: windows.WTD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT | windows.WTD_CACHE_ONLY_URL_RETRIEVAL | windows.WTD_DISABLE_MD2_MD4}
	defer func() {
		data.StateAction = windows.WTD_STATEACTION_CLOSE
		windows.WinVerifyTrustEx(windows.InvalidHWND, &windows.WINTRUST_ACTION_GENERIC_VERIFY_V2, &data)
	}()
	if e = windows.WinVerifyTrustEx(windows.InvalidHWND, &windows.WINTRUST_ACTION_GENERIC_VERIFY_V2, &data); e != nil {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	api := windows.NewLazySystemDLL("wintrust.dll")
	provider, _, _ := api.NewProc("WTHelperProvDataFromStateData").Call(uintptr(data.StateData))
	if provider == 0 {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	signerPtr, _, _ := api.NewProc("WTHelperGetProvSignerFromChain").Call(provider, 0, 0, 0)
	if signerPtr == 0 {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	signer := (*providerSigner)(unsafe.Pointer(signerPtr))
	if signer.Count < 1 || signer.Chain == nil || signer.Chain.Certificate == nil {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	cert := signer.Chain.Certificate
	if cert.Length < 1 || cert.Length > 128<<10 || cert.EncodedCert == nil {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	hash := sha256.Sum256(unsafe.Slice(cert.EncodedCert, cert.Length))
	if hex.EncodeToString(hash[:]) != p.WindowsCertificateSHA256 || ctx.Err() != nil {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	return nil
}
