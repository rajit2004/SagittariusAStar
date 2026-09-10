import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:rhythma/services/local_storage_service.dart';

class ExportService {
  
  static String buildExportJson() {
    final data = _buildExportData();
    return const JsonEncoder.withIndent('  ').convert(data);
  }

  static Map<String, dynamic> _buildExportData() {
    final profile = LocalStorageService.getProfile() ?? {};
    final contacts = LocalStorageService.getEmergencyContacts();
    final cycleLogs = LocalStorageService.getCycleLogs();

    return {
      'export_date': DateTime.now().toIso8601String(),
      'profile': profile,
      'emergency_contacts': contacts,
      'cycle_logs': cycleLogs,
    };
  }

  static Future<void> exportAndShare() async {
    final data = _buildExportData();
    final jsonString =
        const JsonEncoder.withIndent('  ').convert(data);

    final directory = await getTemporaryDirectory();
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    final file = File('${directory.path}/rhythma_export_$timestamp.json');
    await file.writeAsString(jsonString);

    try {
      await Share.shareXFiles(
        [XFile(file.path)],
        subject: 'Rhythma Data Export',
      );
    } catch (_) {
      
    } finally {
      if (await file.exists()) {
        try {
          await file.delete();
        } catch (_) {}
      }
    }
  }
}
