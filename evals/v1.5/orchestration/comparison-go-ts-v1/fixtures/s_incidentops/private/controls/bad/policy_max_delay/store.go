package main

import (
 "database/sql"
 "errors"
 "sort"
)

func migrate(db *sql.DB) error {
 for _, statement := range []string{
  `CREATE TABLE IF NOT EXISTS events (tenant TEXT NOT NULL,event_id TEXT NOT NULL,incident_id TEXT NOT NULL,sequence INTEGER NOT NULL,kind TEXT NOT NULL,occurred_at TEXT NOT NULL,severity TEXT NOT NULL,note TEXT NOT NULL,PRIMARY KEY(tenant,event_id))`,
  `CREATE INDEX IF NOT EXISTS events_incident ON events(tenant,incident_id,sequence,event_id)`,
  `CREATE TABLE IF NOT EXISTS incidents (tenant TEXT NOT NULL,incident_id TEXT NOT NULL,status TEXT NOT NULL,severity TEXT NOT NULL,latest_at TEXT NOT NULL,note TEXT NOT NULL,sequence INTEGER NOT NULL,PRIMARY KEY(tenant,incident_id))`,
  `CREATE TABLE IF NOT EXISTS policies (revision INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,effective_at TEXT NOT NULL,severity TEXT NOT NULL,delay_minutes INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS oncall (revision INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,starts_at TEXT NOT NULL,ends_at TEXT NOT NULL,person TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS outbox (tenant TEXT NOT NULL,incident_id TEXT NOT NULL,generation INTEGER NOT NULL,due_at TEXT NOT NULL,assignee TEXT NOT NULL,state TEXT NOT NULL,PRIMARY KEY(tenant,incident_id,generation))`,
 } { if _,err:=db.Exec(statement);err!=nil{return err} }
 cols,err:=db.Query(`PRAGMA table_info(incidents)`);if err!=nil{return err};hasSequence:=false
 for cols.Next(){var n int;var name,typ string;var notNull,pk int;var def sql.NullString;if err=cols.Scan(&n,&name,&typ,&notNull,&def,&pk);err!=nil{cols.Close();return err};if name=="sequence"{hasSequence=true}}
 err=cols.Err();cols.Close();if err!=nil{return err}
 if !hasSequence {if _,err=db.Exec(`ALTER TABLE incidents ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0`);err!=nil{return err}}
 tenants,err:=db.Query(`SELECT DISTINCT tenant FROM events`);if err!=nil{return err};names:=[]string{};for tenants.Next(){var name string;if err=tenants.Scan(&name);err!=nil{tenants.Close();return err};names=append(names,name)};err=tenants.Err();tenants.Close();if err!=nil{return err}
 tx,err:=db.Begin();if err!=nil{return err};defer tx.Rollback();for _,tenant:=range names{if err=rebuildTenant(tx,tenant);err!=nil{return err}};return tx.Commit()
}

type effect struct { Generation int `json:"generation"`; DueAt string `json:"due_at"`; Assignee string `json:"assignee"`; State string `json:"state"` }
var invalidTransition=errors.New("invalid transition")

func rebuild(tx *sql.Tx,tenant,id string) (Incident,error) {
 rows,err:=tx.Query(`SELECT event_id,incident_id,sequence,kind,occurred_at,severity,note FROM events WHERE tenant=? AND incident_id=? ORDER BY sequence,event_id`,tenant,id)
 if err!=nil{return Incident{},err}
 events:=[]Event{}
 for rows.Next(){var e Event;if err=rows.Scan(&e.EventID,&e.IncidentID,&e.Sequence,&e.Kind,&e.OccurredAt,&e.Severity,&e.Note);err!=nil{rows.Close();return Incident{},err};events=append(events,e)}
 err=rows.Err();rows.Close();if err!=nil{return Incident{},err}
 if len(events)==0{return Incident{},invalidTransition}
 current:=Incident{ID:id};status:="";generation:=0;effects:=[]effect{}
 for _,e:=range events {
  switch e.Kind {
  case "OPEN": if status!="" {return Incident{},invalidTransition};status="open";generation++;current.Severity=e.Severity;effects=append(effects,effect{Generation:generation,DueAt:e.OccurredAt,State:"pending"})
  case "ACK": if status!="open" {return Incident{},invalidTransition};status="acknowledged";effects[len(effects)-1].State="cancelled"
  case "RESOLVE": if status!="open"&&status!="acknowledged" {return Incident{},invalidTransition};status="resolved";effects[len(effects)-1].State="cancelled"
  case "REOPEN": if status!="resolved" {return Incident{},invalidTransition};status="open";generation++;current.Severity=e.Severity;effects=append(effects,effect{Generation:generation,DueAt:e.OccurredAt,State:"pending"})
  default:return Incident{},invalidTransition
  }
  current.Status=status;current.LatestAt=e.OccurredAt;current.Note=e.Note;current.Sequence=e.Sequence
 }
 _,err=tx.Exec(`INSERT INTO incidents(tenant,incident_id,status,severity,latest_at,note,sequence) VALUES(?,?,?,?,?,?,?) ON CONFLICT(tenant,incident_id) DO UPDATE SET status=excluded.status,severity=excluded.severity,latest_at=excluded.latest_at,note=excluded.note,sequence=excluded.sequence`,tenant,id,current.Status,current.Severity,current.LatestAt,current.Note,current.Sequence)
 if err!=nil{return Incident{},err}
 for i:=range effects {
  e:=&effects[i]
  start:=events[0]
  count:=0
  for _,item:=range events {if item.Kind=="OPEN"||item.Kind=="REOPEN" {count++;if count==e.Generation {start=item;break}}}
  var delay int
  err=tx.QueryRow(`SELECT delay_minutes FROM policies WHERE tenant=? AND severity=? AND effective_at<=? ORDER BY delay_minutes DESC,revision DESC LIMIT 1`,tenant,start.Severity,start.OccurredAt).Scan(&delay)
  if err==sql.ErrNoRows {delay=60}else if err!=nil{return Incident{},err}
  due,err:=addMinutes(start.OccurredAt,delay);if err!=nil{return Incident{},err};e.DueAt=due
  err=tx.QueryRow(`SELECT person FROM oncall WHERE tenant=? AND starts_at<=? AND ends_at>? ORDER BY starts_at DESC,revision DESC LIMIT 1`,tenant,due,due).Scan(&e.Assignee)
  if err==sql.ErrNoRows{e.Assignee="unassigned"}else if err!=nil{return Incident{},err}
  var oldState string
  oldErr:=tx.QueryRow(`SELECT state FROM outbox WHERE tenant=? AND incident_id=? AND generation=?`,tenant,id,e.Generation).Scan(&oldState)
  if oldErr!=nil&&oldErr!=sql.ErrNoRows{return Incident{},oldErr}
  if oldState=="cancelled" {e.State="cancelled"}
  _,err=tx.Exec(`INSERT INTO outbox(tenant,incident_id,generation,due_at,assignee,state) VALUES(?,?,?,?,?,?) ON CONFLICT(tenant,incident_id,generation) DO UPDATE SET due_at=excluded.due_at,assignee=excluded.assignee,state=excluded.state`,tenant,id,e.Generation,e.DueAt,e.Assignee,e.State)
  if err!=nil{return Incident{},err}
 }
 return current,nil
}

func rebuildTenant(tx *sql.Tx,tenant string)error{
 rows,err:=tx.Query(`SELECT incident_id FROM incidents WHERE tenant=?`,tenant);if err!=nil{return err};ids:=[]string{};for rows.Next(){var id string;if err=rows.Scan(&id);err!=nil{rows.Close();return err};ids=append(ids,id)};err=rows.Err();rows.Close();if err!=nil{return err};sort.Strings(ids)
 for _,id:=range ids{if _,err=rebuild(tx,tenant,id);err!=nil{return err}}
 return nil
}
