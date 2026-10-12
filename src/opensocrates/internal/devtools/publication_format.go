package devtools

import (
	"bytes"
	"errors"
	"flag"
	"go/format"
	"io"
	"os"
	"path/filepath"
	"sort"
)

// RunFormat uses Go's parser/formatter directly so checking never depends on a
// shell wrapper or a second language runtime.
func RunFormat(root string, args []string) error {
	flags := flag.NewFlagSet("format", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	check := flags.Bool("check", false, "report formatting differences without edits")
	flags.StringVar(&root, "root", root, "checkout root")
	if err := flags.Parse(args); err != nil || len(flags.Args()) != 0 {
		return errors.New("format_arguments_invalid")
	}
	files := []string{}
	err := filepath.WalkDir(filepath.Join(root, "src", "opensocrates"), func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return errors.New("format_source_link_forbidden")
		}
		if !entry.IsDir() && filepath.Ext(path) == ".go" {
			files = append(files, path)
		}
		return nil
	})
	if err != nil {
		return err
	}
	sort.Strings(files)
	changed := false
	for _, path := range files {
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		formatted, err := format.Source(data)
		if err != nil {
			return errors.New("format_go_parse_failed")
		}
		if bytes.Equal(data, formatted) {
			continue
		}
		changed = true
		if !*check {
			if err = os.WriteFile(path, formatted, 0644); err != nil {
				return err
			}
		}
	}
	if *check && changed {
		return errors.New("format_changes_required")
	}
	return nil
}
