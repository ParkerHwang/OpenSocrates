package main

type Event struct {
 EventID string `json:"event_id"`
 IncidentID string `json:"incident_id"`
 Sequence int `json:"sequence"`
 Kind string `json:"kind"`
 OccurredAt string `json:"occurred_at"`
 Severity string `json:"severity,omitempty"`
 Note string `json:"note,omitempty"`
}

type Incident struct {
 ID string `json:"incident_id"`
 Status string `json:"status"`
 Severity string `json:"severity"`
 LatestAt string `json:"latest_at"`
 Note string `json:"note"`
}
