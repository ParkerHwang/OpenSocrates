package management

import (
	"bytes"
	"encoding/json"
	"testing"
)

func TestTrustResetRetainsEveryUnownedByte(t *testing.T) {
	original := []byte("\xef\xbb\xbf# 한글😀\r\nmodel = \"same\"\r\n[hooks.state]\r\n# keep\r\n")
	expected := append([]byte{}, original...)
	for _, event := range codexTrustEvents {
		key, _ := json.Marshal(codexTrustPrefix + event + ":0:0")
		original = append(original, []byte("  [hooks.state."+string(key)+"]  # header\r\n\ttrusted_hash = \"hash-"+event+"\"  # hash\r\n")...)
		expected = append(expected, []byte("    # header\r\n\t  # hash\r\n")...)
	}
	tail := []byte("[hooks.state.\"other@other:hooks/hooks.json:stop:0:0\"]\r\ntrusted_hash = \"foreign\"\r\n[future]\r\nbig = 9223372036854775807\r\ntext = '''\r\n[hooks.state.\"opensocrates@opensocrates:hooks/hooks.json:stop:0:0\"]\r\n'''")
	original = append(original, tail...)
	expected = append(expected, tail...)
	reset, e := StripCodexTrust(original)
	if e != nil {
		t.Fatal(e)
	}
	if !bytes.Equal(reset.Contents, expected) || len(reset.RemovedEvents) != 7 {
		t.Fatalf("unowned TOML bytes changed: got %q", reset.Contents)
	}
	again, e := StripCodexTrust(reset.Contents)
	if e != nil || len(again.RemovedEvents) != 0 || !bytes.Equal(again.Contents, expected) {
		t.Fatal("trust reset is not idempotent")
	}
}

func TestTrustResetRejectsUnsupportedOwnedShapes(t *testing.T) {
	key := codexTrustPrefix + "stop:0:0"
	for _, source := range []string{
		"[hooks.state.'" + key + "']\ntrusted_hash = \"x\"\n",
		"[ hooks.state.\"" + key + "\"]\ntrusted_hash = \"x\"\n",
		"[hooks.state.\"" + key + "\"]\nextra = true\ntrusted_hash = \"x\"\n",
		"[hooks.state.\"" + key + "\"]\ntrusted_hash = '''x'''\n",
		"[hooks.state.\"" + key + "\"]\ntrusted_hash = \"\"\"x\"\"\"\n",
		"[hooks.state.\"" + key + "\"]\n# missing hash\n",
		"[hooks.state.\"" + codexTrustPrefix + "stop:1:0\"]\ntrusted_hash = \"x\"\n",
		"hooks.state.\"" + key + "\".trusted_hash = \"x\"\n",
		"[hooks.state]\n\"" + key + "\" = {trusted_hash = \"x\"}\n",
		"hooks = {state = {\"" + key + "\" = {trusted_hash = \"x\"}}}\n",
		"[[hooks.state.\"" + key + "\"]]\ntrusted_hash = \"x\"\n",
		"[hooks.state.\"" + key + "\"]\ntrusted_hash = null\n",
		"[hooks.state.\"" + key + "\"]\ntrusted_hash = \"x\"\ntrusted_hash = \"again\"\n",
	} {
		t.Run(source, func(t *testing.T) {
			if _, e := StripCodexTrust([]byte(source)); e == nil {
				t.Fatal("unsupported namespace shape was mutated")
			}
		})
	}
	if _, e := StripCodexTrust([]byte{255}); e == nil {
		t.Fatal("invalid UTF-8 accepted")
	}
}

func TestTrustResetPreservesUnrelatedNullableSyntaxAndUnicode(t *testing.T) {
	source := []byte("[other]\ntext = \"한글 \\\" quote\"\narray = [1, 2, 3]\nfuture = {foo = 'empty', unknown = []}\n[hooks.state.\"foreign\"]\ntrusted_hash = ''\n")
	reset, e := StripCodexTrust(source)
	if e != nil || !bytes.Equal(reset.Contents, source) || len(reset.RemovedEvents) != 0 {
		t.Fatal("unrelated TOML modified")
	}
}

func FuzzTrustReset(f *testing.F) {
	f.Add([]byte("[hooks.state.\"" + codexTrustPrefix + "stop:0:0\"]\ntrusted_hash = \"value\"\n"))
	f.Add([]byte("# 한글😀\n[other]\nkey = \"same\"\n"))
	f.Fuzz(func(t *testing.T, b []byte) {
		if len(b) > 64<<10 {
			t.Skip()
		}
		r, e := StripCodexTrust(b)
		if e != nil {
			return
		}
		again, e := StripCodexTrust(r.Contents)
		if e != nil || len(again.RemovedEvents) != 0 || !bytes.Equal(again.Contents, r.Contents) {
			t.Fatal("successful reset not stable")
		}
	})
}
