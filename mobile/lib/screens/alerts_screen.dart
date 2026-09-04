import 'package:flutter/material.dart';
import '../models/alert.dart';
import '../services/api_client.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  List<Alert> _alerts = [];
  bool _loading = true;
  int _offset = 0;
  static const _limit = 20;
  bool _hasMore = true;

  @override
  void initState() {
    super.initState();
    _loadAlerts();
  }

  Future<void> _loadAlerts({bool refresh = false}) async {
    if (refresh) {
      _offset = 0;
      _hasMore = true;
    }
    setState(() => _loading = true);
    try {
      final data =
          await ApiClient.get('/alerts?limit=$_limit&offset=$_offset');
      final newAlerts =
          (data as List).map((a) => Alert.fromJson(a)).toList();
      setState(() {
        if (refresh) {
          _alerts = newAlerts;
        } else {
          _alerts.addAll(newAlerts);
        }
        _hasMore = newAlerts.length == _limit;
        _offset += newAlerts.length;
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  Future<void> _acknowledgeAlert(Alert alert) async {
    try {
      await ApiClient.patch('/alerts/${alert.id}/ack', {
        'acknowledged': true,
      });
      _loadAlerts(refresh: true);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  void _showAlertImage(Alert alert) {
    if (alert.imagePath == null) return;
    showDialog(
      context: context,
      builder: (_) => Dialog(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AppBar(
              title: Text('Alert #${alert.id}'),
              automaticallyImplyLeading: false,
              actions: [
                IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context)),
              ],
            ),
            Image.network(
              '${ApiClient.baseUrl.replaceFirst('/api/v1', '')}/api/v1/alerts/${alert.id}/image',
              errorBuilder: (_, __, ___) =>
                  const Padding(
                    padding: EdgeInsets.all(32),
                    child: Text('Failed to load image'),
                  ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Type: ${alert.alertType}'),
                  Text(
                      'Confidence: ${(alert.confidence * 100).toStringAsFixed(1)}%'),
                  Text('Time: ${alert.createdAt}'),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Alerts')),
      body: _loading && _alerts.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: () => _loadAlerts(refresh: true),
              child: _alerts.isEmpty
                  ? const Center(child: Text('No alerts'))
                  : ListView.builder(
                      itemCount: _alerts.length + (_hasMore ? 1 : 0),
                      itemBuilder: (_, i) {
                        if (i == _alerts.length) {
                          // Load more trigger
                          _loadAlerts();
                          return const Padding(
                            padding: EdgeInsets.all(16),
                            child:
                                Center(child: CircularProgressIndicator()),
                          );
                        }
                        final a = _alerts[i];
                        return Card(
                          margin: const EdgeInsets.symmetric(
                              horizontal: 16, vertical: 4),
                          color: a.acknowledged
                              ? null
                              : Theme.of(context)
                                  .colorScheme
                                  .errorContainer,
                          child: ListTile(
                            leading: Icon(
                              Icons.warning_amber,
                              color: a.acknowledged
                                  ? Colors.grey
                                  : Colors.red,
                              size: 32,
                            ),
                            title: Text(
                                '${a.alertType} — ${(a.confidence * 100).toStringAsFixed(0)}%'),
                            subtitle: Text(
                                'Device #${a.deviceId} • ${a.createdAt}'),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                if (a.imagePath != null)
                                  IconButton(
                                    icon: const Icon(Icons.image),
                                    onPressed: () => _showAlertImage(a),
                                  ),
                                if (!a.acknowledged)
                                  IconButton(
                                    icon: const Icon(Icons.check),
                                    tooltip: 'Acknowledge',
                                    onPressed: () =>
                                        _acknowledgeAlert(a),
                                  ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
    );
  }
}
