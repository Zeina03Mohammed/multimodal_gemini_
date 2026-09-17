import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'api_config.dart';

class GeneratePage extends StatefulWidget {
  const GeneratePage({super.key});

  @override
  State<GeneratePage> createState() => _GeneratePageState();
}

class _GeneratePageState extends State<GeneratePage> {
  final _promptController = TextEditingController();
  final _systemController = TextEditingController();

  bool _loading = false;
  String? _error;
  String? _content;
  String? _model;
  int? _inputTokens;
  int? _outputTokens;

  @override
  void dispose() {
    _promptController.dispose();
    _systemController.dispose();
    super.dispose();
  }

  Future<void> _generate() async {
    final prompt = _promptController.text.trim();
    if (prompt.isEmpty) {
      setState(() => _error = 'Please enter a prompt.');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
      _content = null;
    });

    try {
      final response = await http.post(
        Uri.parse('$apiBaseUrl/generate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'prompt': prompt,
          if (_systemController.text.trim().isNotEmpty)
            'system': _systemController.text.trim(),
        }),
      );

      if (response.statusCode != 200) {
        throw Exception(extractErrorDetail(response));
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      setState(() {
        _content = data['content'] as String;
        _model = data['model'] as String;
        _inputTokens = data['input_tokens'] as int;
        _outputTokens = data['output_tokens'] as int;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 640),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                controller: _systemController,
                decoration: const InputDecoration(
                  labelText: 'System instruction (optional)',
                  hintText: 'e.g. You are a witty copywriter.',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _promptController,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: 'Prompt',
                  hintText: 'What do you want to generate?',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _loading ? null : _generate,
                child: _loading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Generate'),
              ),
              const SizedBox(height: 24),
              if (_error != null)
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              if (_content != null) ...[
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: SelectableText(_content!),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '$_model  •  $_inputTokens in / $_outputTokens out tokens',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
