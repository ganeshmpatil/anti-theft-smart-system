import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:open_filex/open_filex.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:http/http.dart' as http;

const _repoOwner = 'ganeshmpatil';
const _repoName = 'anti-theft-smart-system';

class AppUpdate {
  final String version;
  final String downloadUrl;
  final String releaseNotes;

  AppUpdate({
    required this.version,
    required this.downloadUrl,
    required this.releaseNotes,
  });
}

class UpdateService {
  /// Check GitHub releases for a newer version.
  /// Returns [AppUpdate] if update available, null otherwise.
  static Future<AppUpdate?> checkForUpdate() async {
    if (kIsWeb) return null;

    try {
      final response = await http.get(Uri.parse(
        'https://api.github.com/repos/$_repoOwner/$_repoName/releases/latest',
      ));

      if (response.statusCode != 200) {
        debugPrint('[UpdateService] GitHub API returned ${response.statusCode}');
        return null;
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final tagName = data['tag_name'] as String? ?? '';
      final releaseVersion = tagName.replaceFirst(RegExp(r'^v'), '');
      final releaseNotes = data['body'] as String? ?? '';

      final info = await PackageInfo.fromPlatform();
      final currentVersion = info.version;

      if (!_isNewer(releaseVersion, currentVersion)) {
        debugPrint('[UpdateService] Current $currentVersion is up to date (latest: $releaseVersion)');
        return null;
      }

      // Find APK asset in release
      final assets = data['assets'] as List<dynamic>? ?? [];
      String? apkUrl;
      for (final asset in assets) {
        final name = asset['name'] as String? ?? '';
        if (name.endsWith('.apk')) {
          apkUrl = asset['browser_download_url'] as String?;
          break;
        }
      }

      if (apkUrl == null) {
        debugPrint('[UpdateService] No APK found in release $releaseVersion');
        return null;
      }

      debugPrint('[UpdateService] Update available: $currentVersion -> $releaseVersion');
      return AppUpdate(
        version: releaseVersion,
        downloadUrl: apkUrl,
        releaseNotes: releaseNotes,
      );
    } catch (e) {
      debugPrint('[UpdateService] Check failed: $e');
      return null;
    }
  }

  /// Download APK and trigger installation.
  /// [onProgress] reports 0.0 to 1.0.
  static Future<bool> downloadAndInstall(
    String url, {
    void Function(double progress)? onProgress,
  }) async {
    try {
      final dir = await getExternalCacheDirectories();
      final downloadDir = dir?.isNotEmpty == true
          ? dir!.first
          : await getTemporaryDirectory();
      final filePath = '${downloadDir.path}/farmguard_update.apk';

      // Delete old APK if exists
      final oldFile = File(filePath);
      if (oldFile.existsSync()) {
        oldFile.deleteSync();
      }

      final dio = Dio();
      await dio.download(
        url,
        filePath,
        onReceiveProgress: (received, total) {
          if (total > 0) {
            onProgress?.call(received / total);
          }
        },
      );

      debugPrint('[UpdateService] APK downloaded to $filePath');

      // Trigger install
      final result = await OpenFilex.open(filePath,
          type: 'application/vnd.android.package-archive');

      if (result.type != ResultType.done) {
        debugPrint('[UpdateService] Failed to open APK: ${result.message}');
        return false;
      }

      return true;
    } catch (e) {
      debugPrint('[UpdateService] Download/install failed: $e');
      return false;
    }
  }

  /// Compare semantic versions. Returns true if [newVersion] > [current].
  static bool _isNewer(String newVersion, String current) {
    final newParts = newVersion.split('.').map((e) => int.tryParse(e) ?? 0).toList();
    final curParts = current.split('.').map((e) => int.tryParse(e) ?? 0).toList();

    for (var i = 0; i < 3; i++) {
      final n = i < newParts.length ? newParts[i] : 0;
      final c = i < curParts.length ? curParts[i] : 0;
      if (n > c) return true;
      if (n < c) return false;
    }
    return false;
  }
}
