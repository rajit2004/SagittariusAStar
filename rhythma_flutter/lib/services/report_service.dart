import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:rhythma/services/local_storage_service.dart';
import 'package:rhythma/services/api_client.dart';
import 'package:rhythma/services/assistant_service.dart';

class ReportService {
  static Future<void> generateAndShareReport() async {
    final profile = LocalStorageService.getProfile() ?? {};
    final contacts = LocalStorageService.getEmergencyContacts();
    final cycleLogs = LocalStorageService.getCycleLogs();
    final reportDate = DateTime.now();
    final symptoms = cycleLogs.expand((log) => log['symptoms'] ?? []).toList();

    Map<String, dynamic> dashboard = {};

    try {
      final response = await ApiClient.dio.get('/dashboard');
      dashboard = Map<String, dynamic>.from(response.data);
    } catch (_) {}

    String aiSummary = 'No AI summary available';

    try {
      final assistant = AssistantService();
      aiSummary = await assistant.chat(
        'Generate a short health summary based on my recent cycle data.',
      );
    } catch (_) {}
    final pdf = pw.Document();

    pdf.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        build: (context) => [
          pw.Header(
            level: 0,
            child: pw.Text(
              'Rhythma Health Report',
              style: pw.TextStyle(
                fontSize: 24,
                fontWeight: pw.FontWeight.bold,
              ),
            ),
          ),
          pw.SizedBox(height: 10),
          pw.Text(
            'Generated on: ${reportDate.day}/${reportDate.month}/${reportDate.year}',
          ),
          pw.SizedBox(height: 20),
          pw.Text(
            'Profile',
            style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 16),
          ),
          pw.SizedBox(height: 8),
          if (profile.isNotEmpty) ...[
            _buildProfileRow('Name', profile['name'] ?? 'N/A'),
            _buildProfileRow('Age', profile['age']?.toString() ?? 'N/A'),
            _buildProfileRow('Weight', profile['weight']?.toString() ?? 'N/A'),
            _buildProfileRow('Height', profile['height']?.toString() ?? 'N/A'),
          ] else
            pw.Text('No profile data available'),
          pw.SizedBox(height: 20),
          pw.Text(
            'Emergency Contacts',
            style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 16),
          ),
          pw.SizedBox(height: 8),
          if (contacts.isNotEmpty)
            ...contacts.map(
              (c) => pw.Text(
                '${c['name'] ?? 'N/A'} - ${c['phone'] ?? 'N/A'}',
              ),
            )
          else
            pw.Text('No emergency contacts added'),
          pw.SizedBox(height: 20),
          pw.Text(
            'Cycle History',
            style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 16),
          ),
          pw.SizedBox(height: 8),
          if (cycleLogs.isEmpty)
            pw.Text('No cycle history available')
          else
            ...cycleLogs.map(
              (log) => pw.Text(
                '${log['date'] ?? 'N/A'}: Flow ${log['flow'] ?? 'N/A'}, Mood ${log['mood'] ?? 'N/A'}',
              ),
            ),
          pw.SizedBox(height: 20),
          pw.Text(
            'Symptoms',
            style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 16),
          ),
          pw.SizedBox(height: 8),
          if (symptoms.isEmpty)
            pw.Text('No symptoms logged')
          else
            ...symptoms.map(
              (symptom) => pw.Text('- $symptom'),
            ),
          pw.SizedBox(height: 20),
          pw.Text(
            'AI Health Summary',
            style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 16),
          ),
          pw.SizedBox(height: 8),
          pw.Text(aiSummary),
          pw.SizedBox(height: 20),
          pw.Text(
            'Health Insights',
            style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 16),
          ),
          pw.SizedBox(height: 8),
          pw.Text(
            'Avg Cycle Length: ${dashboard['insights']?['averageCycleLength'] ?? 'N/A'} days',
          ),
          pw.Text(
            'Avg Bleeding Duration: ${dashboard['insights']?['averageBleedingDuration'] ?? 'N/A'} days',
          ),
          pw.Text(
            'Sleep Hours: ${dashboard['insights']?['sleepHours'] ?? 'N/A'}',
          ),
          pw.Text(
            'Recent Stress Level: ${dashboard['recentStressLevel'] ?? 'N/A'}',
          ),
          pw.SizedBox(height: 24),
          pw.Divider(),
          pw.SizedBox(height: 8),
          pw.Text(
            'This report is an estimate based on self-logged data and is not a medical diagnosis. Please consult a qualified healthcare professional for medical advice.',
            style: pw.TextStyle(fontSize: 9, color: PdfColors.grey700),
          ),
        ],
      ),
    );

    final bytes = await pdf.save();

    await Printing.sharePdf(
      bytes: bytes,
      filename: 'rhythma_health_report.pdf',
    );
  }

  static pw.Widget _buildProfileRow(String label, String value) {
    return pw.Padding(
      padding: const pw.EdgeInsets.only(bottom: 4),
      child: pw.Row(
        children: [
          pw.SizedBox(
            width: 120,
            child: pw.Text(
              label,
              style: pw.TextStyle(fontWeight: pw.FontWeight.bold),
            ),
          ),
          pw.Expanded(child: pw.Text(value)),
        ],
      ),
    );
  }
}
