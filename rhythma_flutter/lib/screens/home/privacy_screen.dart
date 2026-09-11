import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../components/shared.dart';

class PrivacyScreen extends StatelessWidget {
  const PrivacyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(gradient: RhythmaGradients.bg),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: const Text('Privacy & Security'),
          centerTitle: true,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded),
            onPressed: () => Navigator.pop(context),
          ),
        ),
        body: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildSection(
                icon: Icons.storage_rounded,
                color: RhythmaColors.teal,
                title: 'Data Storage',
                body:
                    'Your health data is stored locally on your device using encrypted storage. '
                    'This means your cycle logs, symptoms, and personal information never leave your phone unless you choose to sync.',
              ),
              _buildSection(
                icon: Icons.cloud_rounded,
                color: RhythmaColors.primary,
                title: 'Cloud Sync',
                body:
                    'If you enable cloud sync, your data is securely backed up to Firebase Firestore. '
                    'This allows you to access your data across devices and ensures you never lose your records. '
                    'Sync can be disabled at any time from Settings.',
              ),
              _buildSection(
                icon: Icons.lock_rounded,
                color: RhythmaColors.coral,
                title: 'Encryption',
                body:
                    'Your authentication tokens are stored using platform-level secure storage '
                    '(Android Keystore / iOS Keychain). Sensitive data is encrypted at rest and '
                    'all network communications use HTTPS/TLS encryption.',
              ),
              _buildSection(
                icon: Icons.person_off_rounded,
                color: RhythmaColors.rose,
                title: 'No Data Selling',
                body:
                    'Rhythma never sells, shares, or monetizes your personal health data. '
                    'Your information is used solely to provide you with health insights and '
                    'personalized features within the app.',
              ),
              _buildSection(
                icon: Icons.delete_rounded,
                color: RhythmaColors.mutedFg,
                title: 'Delete Your Data',
                body:
                    'You can delete your account and all associated data at any time from '
                    'Settings > Delete Account. This permanently removes your profile, '
                    'cycle logs, chat history, and all other data from our servers.',
              ),
              _buildSection(
                icon: Icons.shield_rounded,
                color: RhythmaColors.teal,
                title: 'AI Assistant',
                body:
                    'The AI health assistant uses Google Gemini to provide health information. '
                    'Your conversations are used to provide contextual responses but are not stored '
                    'permanently. The AI provides general health education and is not a substitute '
                    'for professional medical advice.',
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSection({
    required IconData icon,
    required Color color,
    required String title,
    required String body,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: GlassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                TintedIcon(icon: icon, color: color, size: 36),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    title,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: RhythmaColors.foreground,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              body,
              style: TextStyle(
                fontSize: 14,
                color: RhythmaColors.mutedFg,
                height: 1.5,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
