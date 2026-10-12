package update

import (
	"context"
	"flag"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/theupdateframework/go-tuf/v2/metadata"
	"github.com/theupdateframework/go-tuf/v2/metadata/config"
	"github.com/theupdateframework/go-tuf/v2/metadata/updater"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// MetadataFetchCommand prepares authenticated public release state. It never
// bootstraps trust from the server and never downloads executable targets.
func MetadataFetchCommand(args []string) error {
	fs := flag.NewFlagSet("metadata-fetch", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	out := fs.String("output", "build/previous-metadata", "authenticated publication output")
	initial := fs.Bool("initial-repository", false, "explicit first production repository")
	if fs.Parse(args) != nil || fs.NArg() != 0 {
		return closed(diagnostics.Verification, "metadata_fetch_arguments")
	}
	repo := DefaultRepository()
	if ValidateProductionRoot(repo.BootstrapRoot, time.Now().UTC()) != nil {
		return closed(diagnostics.HostUnavailable, "trust_root")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	downloaded := map[string][]byte{}
	f := &Transport{Context: ctx, AllowedHosts: repo.AllowedHosts, OnDownloaded: func(raw string, b []byte) {
		name := filepath.Base(raw)
		if strings.HasSuffix(name, ".root.json") {
			downloaded[name] = append([]byte(nil), b...)
		}
	}}
	if *initial {
		for _, name := range []string{"timestamp.json", "snapshot.json", "targets.json"} {
			_, err := f.DownloadFile(repo.MetadataURL+name, 5<<20, 0)
			if h, ok := err.(*metadata.ErrDownloadHTTP); !ok || h.StatusCode != http.StatusNotFound {
				return closed(diagnostics.Verification, "initial_repository_exists")
			}
		}
		return nil
	}
	scratch, err := os.MkdirTemp("", "opensocrates-sign-metadata-")
	if err != nil {
		return closed(diagnostics.Permission, "metadata_fetch")
	}
	defer os.RemoveAll(scratch)
	cfg, err := config.New(repo.MetadataURL, repo.BootstrapRoot)
	if err != nil {
		return closed(diagnostics.Verification, "metadata_fetch")
	}
	cfg.LocalMetadataDir = scratch
	cfg.LocalTargetsDir = filepath.Join(scratch, "targets")
	cfg.Fetcher = f
	cfg.MaxRootRotations = 32
	cfg.MaxDelegations = 8
	u, err := updater.New(cfg)
	if err != nil {
		return closed(diagnostics.Verification, "metadata_fetch")
	}
	if u.Refresh() != nil {
		return closed(diagnostics.Verification, "metadata_fetch")
	}
	if os.MkdirAll(*out, 0755) != nil {
		return closed(diagnostics.Permission, "metadata_fetch")
	}
	for _, name := range []string{"root.json", "targets.json", "snapshot.json", "timestamp.json"} {
		b, err := readReleaseInput(filepath.Join(scratch, name), 5<<20)
		if err != nil {
			return err
		}
		if os.WriteFile(filepath.Join(*out, name), b, 0644) != nil {
			return closed(diagnostics.Permission, "metadata_fetch")
		}
	}
	anchor, _ := metadata.Root().FromBytes(repo.BootstrapRoot)
	downloaded[fmtVersion(anchor.Signed.Version)+".root.json"] = repo.BootstrapRoot
	for name, b := range downloaded {
		if os.WriteFile(filepath.Join(*out, name), b, 0644) != nil {
			return closed(diagnostics.Permission, "metadata_fetch")
		}
	}
	return nil
}
func fmtVersion(v int64) string { return strconv.FormatInt(v, 10) }
