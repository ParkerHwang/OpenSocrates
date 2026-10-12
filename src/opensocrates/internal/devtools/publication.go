package devtools

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

const publicationRepository = "ParkerHwang/OpenSocrates"

var publicationCommitPattern = regexp.MustCompile(`^[0-9a-f]{40}$`)
var publicationVersionPattern = regexp.MustCompile(`^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`)
var publicationHashPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)

type publicationOptions struct{ root, output, expected, repository, target string }

// RunPublication executes Go-only release gates. Publication requires the exact
// reviewed remote tag and an approved Actions release environment; it cannot
// publish an arbitrary branch or overwrite an existing release.
func RunPublication(root, command string, args []string) error {
	o := publicationOptions{root: root}
	f := flag.NewFlagSet(command, flag.ContinueOnError)
	f.SetOutput(io.Discard)
	f.StringVar(&o.root, "root", root, "source checkout")
	f.StringVar(&o.output, "output", "", "output receipt")
	f.StringVar(&o.expected, "commit", os.Getenv("OPENSOCRATES_EXPECTED_SOURCE_SHA"), "expected source commit")
	f.StringVar(&o.repository, "repo", publicationRepository, "repository")
	f.StringVar(&o.target, "target", "", "native target")
	if err := f.Parse(args); err != nil {
		return errors.New("release_arguments_invalid")
	}
	if len(f.Args()) != 0 || o.repository != publicationRepository {
		return errors.New("release_arguments_invalid")
	}
	absolute, err := filepath.Abs(o.root)
	if err != nil {
		return err
	}
	o.root = absolute
	switch command {
	case "release-identity":
		_, err = publicationIdentity(o.root)
		return err
	case "release-immutability":
		if err = publicationRequireEnvironment(); err != nil {
			return err
		}
		if _, err = publicationIdentity(o.root); err != nil {
			return err
		}
		return publicationImmutableEnabled()
	case "release-provenance":
		return publicationProvenance(o)
	case "release-merge-windows":
		return publicationMerge(o)
	case "release-finalize":
		return publicationFinalize(o)
	case "release-sign":
		return publicationSign(o)
	case "release-notarize":
		return publicationNotarize(o)
	case "release-publish":
		return publicationPublish(o)
	case "release-verify-public":
		return publicationVerifyPublic(o)
	default:
		return errors.New("release_command_unknown")
	}
}

func publicationGit(root string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "git", args...)
	cmd.Dir = root
	output, err := cmd.Output()
	if err != nil {
		return "", errors.New("release_git_inspection_failed")
	}
	if len(output) > 1024*1024 {
		return "", errors.New("release_git_response_oversize")
	}
	return strings.TrimSpace(string(output)), nil
}

func publicationRemoteTag(output, tag string) (string, error) {
	refs := map[string]string{}
	for _, row := range strings.Split(strings.TrimSpace(output), "\n") {
		fields := strings.Fields(row)
		if len(fields) != 2 || !publicationCommitPattern.MatchString(fields[0]) || (fields[1] != "refs/tags/"+tag && fields[1] != "refs/tags/"+tag+"^{}") || refs[fields[1]] != "" {
			return "", errors.New("release_remote_tag_invalid")
		}
		refs[fields[1]] = fields[0]
	}
	if refs["refs/tags/"+tag] == "" {
		return "", errors.New("release_remote_tag_missing")
	}
	if peeled := refs["refs/tags/"+tag+"^{}"]; peeled != "" {
		return peeled, nil
	}
	return refs["refs/tags/"+tag], nil
}

func publicationVersion(root string) (string, error) {
	data, err := os.ReadFile(filepath.Join(root, "VERSION"))
	if err != nil {
		return "", err
	}
	version := strings.TrimSpace(string(data))
	if !publicationVersionPattern.MatchString(version) {
		return "", errors.New("release_version_invalid")
	}
	return version, nil
}

func publicationIdentity(root string) (string, error) {
	version, err := publicationVersion(root)
	if err != nil {
		return "", err
	}
	commit := os.Getenv("GITHUB_SHA")
	tag := "v" + version
	if !publicationCommitPattern.MatchString(commit) || os.Getenv("GITHUB_REF") != "refs/tags/"+tag || os.Getenv("GITHUB_REPOSITORY") != publicationRepository {
		return "", errors.New("release_exact_tag_required")
	}
	head, err := publicationGit(root, "rev-parse", "HEAD")
	if err != nil || head != commit {
		return "", errors.New("release_checkout_mismatch")
	}
	status, err := publicationGit(root, "status", "--porcelain", "--untracked-files=no")
	if err != nil || status != "" {
		return "", errors.New("release_source_dirty")
	}
	output, err := publicationGit(root, "ls-remote", "--tags", "origin", "refs/tags/"+tag, "refs/tags/"+tag+"^{}")
	if err != nil {
		return "", err
	}
	remote, err := publicationRemoteTag(output, tag)
	if err != nil || remote != commit {
		return "", errors.New("release_source_tag_mismatch")
	}
	if _, err = publicationGit(root, "merge-base", "--is-ancestor", commit, "origin/main"); err != nil {
		return "", errors.New("release_source_not_merged")
	}
	return commit, nil
}

func publicationProvenance(o publicationOptions) error {
	if !publicationCommitPattern.MatchString(o.expected) {
		return errors.New("provenance_expected_commit_invalid")
	}
	head, err := publicationGit(o.root, "rev-parse", "HEAD")
	if err != nil || head != o.expected {
		return errors.New("provenance_checkout_mismatch")
	}
	tree, err := publicationGit(o.root, "rev-parse", "HEAD^{tree}")
	if err != nil || !publicationCommitPattern.MatchString(tree) {
		return errors.New("provenance_tree_invalid")
	}
	status, err := publicationGit(o.root, "status", "--porcelain", "--untracked-files=no")
	if err != nil || status != "" {
		return errors.New("provenance_source_dirty")
	}
	output := o.output
	if output == "" {
		output = "build/evidence/package-source-provenance.json"
	}
	if filepath.IsAbs(output) {
		relative, err := filepath.Rel(o.root, output)
		if err != nil {
			return err
		}
		output = relative
	}
	target, err := safeCheckPath(o.root, filepath.ToSlash(output))
	if err != nil {
		return err
	}
	receipt := map[string]any{"schema": "opensocrates.package-source-provenance/1.0.0", "repository": publicationRepository, "commit": head, "tree": tree, "platform": runtime.GOOS + "-" + runtime.GOARCH, "go_version": runtime.Version()}
	return publicationWriteExclusive(target, receipt)
}

func publicationWriteExclusive(path string, value any) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	if err = os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return errors.New("release_receipt_collision")
	}
	_, err = file.Write(data)
	if err == nil {
		err = file.Sync()
	}
	closeErr := file.Close()
	if err == nil {
		err = closeErr
	}
	return err
}

func publicationHash(path string) (string, int64, error) {
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() {
		return "", 0, errors.New("release_asset_not_regular")
	}
	if info.Size() > 1024*1024*1024 {
		return "", 0, errors.New("release_asset_oversize")
	}
	file, err := os.Open(path)
	if err != nil {
		return "", 0, err
	}
	defer file.Close()
	h := sha256.New()
	size, err := io.Copy(h, file)
	if err != nil {
		return "", 0, err
	}
	return hex.EncodeToString(h.Sum(nil)), size, nil
}

func publicationReceipt(root, name string, value any) error {
	path := filepath.Join(root, "build", "evidence", name)
	// Receipts from different runs are replaceable evidence; release assets are not.
	return writeJSON(path, value)
}

func publicationRequireEnvironment() error {
	if os.Getenv("GITHUB_ACTIONS") != "true" || os.Getenv("OPENSOCRATES_RELEASE_APPROVED") != "true" {
		return errors.New("release_approved_environment_required")
	}
	return nil
}

func publicationError(stage string, err error) error {
	if err != nil {
		return fmt.Errorf("%s: %w", stage, err)
	}
	return nil
}
