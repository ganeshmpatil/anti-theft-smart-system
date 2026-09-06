import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../services/alarm_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _urlCtrl = TextEditingController(text: ApiClient.baseUrl);
  bool _saved = false;
  late bool _alarmEnabled;

  @override
  void initState() {
    super.initState();
    _alarmEnabled = AlarmService().alarmEnabled;
  }

  Future<void> _save() async {
    await ApiClient.saveBaseUrl(_urlCtrl.text.trim());
    setState(() => _saved = true);
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _saved = false);
    });
  }

  Future<void> _toggleAlarm(bool value) async {
    await AlarmService().setAlarmEnabled(value);
    setState(() => _alarmEnabled = value);
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Server URL', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            TextField(
              controller: _urlCtrl,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                hintText: 'http://10.0.2.2:8000/api/v1',
              ),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _save,
              child: Text(_saved ? 'Saved!' : 'Save'),
            ),
            const SizedBox(height: 24),
            const Divider(),
            const SizedBox(height: 16),
            SwitchListTile(
              title: const Text('Emergency Alarm'),
              subtitle: const Text(
                'Play loud alarm sound when intrusion is detected',
              ),
              secondary: Icon(
                _alarmEnabled ? Icons.alarm_on : Icons.alarm_off,
                color: _alarmEnabled ? Colors.red : null,
              ),
              value: _alarmEnabled,
              onChanged: _toggleAlarm,
            ),
            const SizedBox(height: 24),
            const Text(
              'For Android emulator use http://10.0.2.2:8000/api/v1\n'
              'For physical device use your PC\'s LAN IP.',
            ),
          ],
        ),
      ),
    );
  }
}
