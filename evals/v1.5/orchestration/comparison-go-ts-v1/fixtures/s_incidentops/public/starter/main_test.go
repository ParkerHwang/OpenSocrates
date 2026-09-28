package main

import (
 "bytes"
 "database/sql"
 "encoding/json"
 "net/http"
 "net/http/httptest"
 "path/filepath"
 "testing"

 _ "github.com/mattn/go-sqlite3"
)

func TestBasicTenantList(t *testing.T) {
 db,err:=sql.Open("sqlite3",filepath.Join(t.TempDir(),"starter.db"));if err!=nil{t.Fatal(err)};defer db.Close()
 if err=migrate(db);err!=nil{t.Fatal(err)}
 server:=(&Server{DB:db}).routes()
 body,_:=json.Marshal(Event{EventID:"starter-1",IncidentID:"demo",Sequence:1,Kind:"OPEN",OccurredAt:"2026-06-01T10:00:00Z",Severity:"P2",Note:"initial"})
 post:=httptest.NewRequest(http.MethodPost,"/api/events",bytes.NewReader(body));post.Header.Set("X-Tenant","north");post.Header.Set("X-Role","operator")
 written:=httptest.NewRecorder();server.ServeHTTP(written,post);if written.Code!=201{t.Fatalf("POST status %d: %s",written.Code,written.Body.String())}
 for tenant,want:=range map[string]int{"north":1,"south":0}{req:=httptest.NewRequest(http.MethodGet,"/api/incidents",nil);req.Header.Set("X-Tenant",tenant);req.Header.Set("X-Role","viewer");got:=httptest.NewRecorder();server.ServeHTTP(got,req);if got.Code!=200{t.Fatal(got.Code)};var result struct{Items []Incident `json:"items"`};if err=json.Unmarshal(got.Body.Bytes(),&result);err!=nil{t.Fatal(err)};if len(result.Items)!=want{t.Fatalf("%s items %d want %d",tenant,len(result.Items),want)}}
}
