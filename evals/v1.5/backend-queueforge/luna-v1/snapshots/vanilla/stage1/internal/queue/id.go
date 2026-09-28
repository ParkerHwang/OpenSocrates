package queue

import (
	"crypto/rand"
	"encoding/hex"
)

func randomHex() string {
	b := make([]byte, 16)
	if _, e := rand.Read(b); e != nil {
		return "fallback"
	}
	return hex.EncodeToString(b)
}
