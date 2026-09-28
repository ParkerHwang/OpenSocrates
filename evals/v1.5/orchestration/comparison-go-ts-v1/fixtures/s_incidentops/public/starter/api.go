package main

import (
 "database/sql"
 "encoding/json"
 "errors"
	"net/http"
	"os"
 "strconv"
 "strings"
 "time"
)

func (s *Server) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) { writeJSON(w, 200, map[string]string{"status":"ok"}) })
	mux.HandleFunc("/api/incidents", s.incidents)
	mux.HandleFunc("/api/events", s.events)
	mux.HandleFunc("/", serveWeb)
	return mux
}

// Keep the small fixed asset set on the ordinary write path. The external
// qualification sandbox does not permit the platform sendfile shortcut.
func serveWeb(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimPrefix(r.URL.Path, "/")
	if name == "" { name = "index.html" }
	contentType := ""
	switch name {
	case "index.html": contentType = "text/html; charset=utf-8"
	case "style.css": contentType = "text/css; charset=utf-8"
	case "app.js", "api.js", "view.js": contentType = "text/javascript; charset=utf-8"
	default: http.NotFound(w,r); return
	}
	data,err := os.ReadFile("web/"+name)
	if err != nil { http.NotFound(w,r); return }
	w.Header().Set("Content-Type",contentType)
	_,_ = w.Write(data)
}

func identity(r *http.Request) (string,string,error) {
	tenant, role := r.Header.Get("X-Tenant"), r.Header.Get("X-Role")
	if tenant == "" || (role != "operator" && role != "viewer") { return "","",errors.New("valid tenant and role required") }
	return tenant,role,nil
}

func writeJSON(w http.ResponseWriter, code int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(value)
}

func (s *Server) incidents(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet { writeJSON(w,405,map[string]string{"error":"method"}); return }
	tenant,_,err := identity(r)
	if err != nil { writeJSON(w,401,map[string]string{"error":err.Error()}); return }
	rows,err := s.DB.Query(`SELECT incident_id,status,severity,latest_at,note FROM incidents WHERE tenant=? ORDER BY latest_at DESC,incident_id ASC`,tenant)
	if err != nil { writeJSON(w,500,map[string]string{"error":"storage"}); return }
	defer rows.Close()
	items:=[]Incident{}
	for rows.Next() {
		var x Incident
		if err=rows.Scan(&x.ID,&x.Status,&x.Severity,&x.LatestAt,&x.Note); err!=nil { writeJSON(w,500,map[string]string{"error":"storage"}); return }
		if status:=r.URL.Query().Get("status"); status!="" && x.Status!=status { continue }
		if severity:=r.URL.Query().Get("severity"); severity!="" && x.Severity!=severity { continue }
		if q:=strings.ToLower(r.URL.Query().Get("q")); q!="" && !strings.Contains(strings.ToLower(x.ID+" "+x.Note),q) { continue }
		items=append(items,x)
	}
	writeJSON(w,200,map[string]any{"items":items})
}

func (s *Server) events(w http.ResponseWriter,r *http.Request) {
	if r.Method!=http.MethodPost { writeJSON(w,405,map[string]string{"error":"method"}); return }
	tenant,role,err:=identity(r)
	if err!=nil { writeJSON(w,401,map[string]string{"error":err.Error()}); return }
	if role!="operator" { writeJSON(w,403,map[string]string{"error":"forbidden"}); return }
	var e Event
	if err=json.NewDecoder(http.MaxBytesReader(w,r.Body,16384)).Decode(&e); err!=nil || e.EventID=="" || e.IncidentID=="" || e.Sequence<1 { writeJSON(w,400,map[string]string{"error":"invalid event"}); return }
	if _,err=time.Parse(time.RFC3339,e.OccurredAt); err!=nil { writeJSON(w,400,map[string]string{"error":"invalid time"}); return }
	if e.Kind!="OPEN" && e.Kind!="ACK" && e.Kind!="RESOLVE" && e.Kind!="REOPEN" { writeJSON(w,400,map[string]string{"error":"invalid kind"}); return }
	tx,err:=s.DB.Begin()
	if err!=nil { writeJSON(w,500,map[string]string{"error":"storage"}); return }
	defer tx.Rollback()
	var prev Event
	err=tx.QueryRow(`SELECT incident_id,sequence,kind,occurred_at,severity,note FROM events WHERE tenant=? AND event_id=?`,tenant,e.EventID).Scan(&prev.IncidentID,&prev.Sequence,&prev.Kind,&prev.OccurredAt,&prev.Severity,&prev.Note)
	if err==nil {
		if prev.IncidentID==e.IncidentID && prev.Sequence==e.Sequence && prev.Kind==e.Kind && prev.OccurredAt==e.OccurredAt && prev.Severity==e.Severity && prev.Note==e.Note { writeJSON(w,200,map[string]string{"result":"duplicate"}) } else { writeJSON(w,409,map[string]string{"error":"event conflict"}) }; return
	}
	if err!=sql.ErrNoRows { writeJSON(w,500,map[string]string{"error":"storage"}); return }
	_,err=tx.Exec(`INSERT INTO events(tenant,event_id,incident_id,sequence,kind,occurred_at,severity,note) VALUES(?,?,?,?,?,?,?,?)`,tenant,e.EventID,e.IncidentID,e.Sequence,e.Kind,e.OccurredAt,e.Severity,e.Note)
	if err!=nil { writeJSON(w,500,map[string]string{"error":"storage"}); return }
	status:="open"
	if e.Kind=="ACK" { status="acknowledged" }; if e.Kind=="RESOLVE" { status="resolved" }
	var oldSeq int
	err=tx.QueryRow(`SELECT MAX(sequence) FROM events WHERE tenant=? AND incident_id=?`,tenant,e.IncidentID).Scan(&oldSeq)
	if err!=nil { writeJSON(w,500,map[string]string{"error":"storage"}); return }
	if oldSeq==e.Sequence {
		_,err=tx.Exec(`INSERT INTO incidents(tenant,incident_id,status,severity,latest_at,note) VALUES(?,?,?,?,?,?) ON CONFLICT(tenant,incident_id) DO UPDATE SET status=excluded.status,severity=CASE WHEN excluded.severity='' THEN incidents.severity ELSE excluded.severity END,latest_at=excluded.latest_at,note=excluded.note`,tenant,e.IncidentID,status,e.Severity,e.OccurredAt,e.Note)
		if err!=nil { writeJSON(w,500,map[string]string{"error":"storage"}); return }
	}
	if err=tx.Commit(); err!=nil { writeJSON(w,500,map[string]string{"error":"storage"}); return }
	writeJSON(w,201,map[string]any{"incident_id":e.IncidentID,"sequence":strconv.Itoa(e.Sequence),"status":status})
}
