"""Versioned own-artifact failure packets; historical feedback remains unchanged."""


def failure_packets(report, source_commit, reproduction):
    packets = []
    for scenario in report.get('scenarios', []):
        if scenario.get('status') == 'pass':
            continue
        observed = [request for request in report.get('requests', []) if request.get('scenario') == scenario['name']]
        packets.append({'scenario':scenario['name'],'status':scenario.get('status'),
                        'error':scenario.get('error'),'source_commit':source_commit,
                        'reproduction':reproduction,'request_response_evidence':observed,
                        'evidence_status':'retained' if observed else 'unassessable',
                        'boundary':'Own synthetic artifact evidence only; no answer or repair supplied.'})
    return packets


def selfcheck():
    report = {'scenarios':[{'name':'zero','status':'fail','error':'expected400 got201'},{'name':'missing','status':'unassessable'}],
              'requests':[{'scenario':'zero','request':{'max_attempts':0},'expected_status':400,'status':201,'response':{'created':True}}]}
    packets = failure_packets(report,'synthetic-source','run checker')
    assert packets[0]['request_response_evidence'][0]['request'] == {'max_attempts':0}
    assert packets[1]['evidence_status'] == 'unassessable' and not packets[1]['request_response_evidence']
    print('PASS: exact failing values and missing evidence preserved; zero model calls')


if __name__ == '__main__':
    selfcheck()
