import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'api_config.dart';

class RagDocument {
  final String documentId;
  final String filename;
  final int chunkCount;

  RagDocument({required this.documentId, required this.filename, required this.chunkCount});

  factory RagDocument.fromJson(Map<String, dynamic> json) => RagDocument(
        documentId: json['document_id'] as String,
        filename: json['filename'] as String,
        chunkCount: json['chunk_count'] as int,
      );
}

class RagSource {
  final String filename;
  final String text;
  final double distance;

  RagSource({required this.filename, required this.text, required this.distance});

  factory RagSource.fromJson(Map<String, dynamic> json) => RagSource(
        filename: json['filename'] as String,
        text: json['text'] as String,
        distance: (json['distance'] as num).toDouble(),
      );
}

class RagPage extends StatefulWidget {
  const RagPage({super.key});

  @override
  State<RagPage> createState() => _RagPageState();
}

class _RagPageState extends State<RagPage> {
  final _questionController = TextEditingController();

  List<RagDocument> _documents = [];
  bool _loadingDocuments = true;
  bool _uploading = false;
  bool _asking = false;
  String? _error;
  String? _answer;
  List<RagSource> _sources = [];

  @override
  void initState() {
    super.initState();
    _loadDocuments();
  }

  @override
  void dispose() {
    _questionController.dispose();
    super.dispose();
  }

  Future<void> _loadDocuments() async {
    setState(() => _loadingDocuments = true);
    try {
      final response = await http.get(Uri.parse('$apiBaseUrl/rag/documents'));
      final data = jsonDecode(response.body) as List<dynamic>;
      setState(() {
        _documents = data.map((d) => RagDocument.fromJson(d as Map<String, dynamic>)).toList();
      });
    } catch (e) {
      setState(() => _error = 'Could not load documents: $e');
    } finally {
      setState(() => _loadingDocuments = false);
    }
  }

  Future<void> _uploadDocument() async {
    final picked = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['txt', 'md', 'pdf'],
      withData: true,
    );
    if (picked == null || picked.files.isEmpty) return;

    final file = picked.files.single;
    if (file.bytes == null) {
      setState(() => _error = 'Could not read the selected file.');
      return;
    }

    setState(() {
      _uploading = true;
      _error = null;
    });

    try {
      final request = http.MultipartRequest('POST', Uri.parse('$apiBaseUrl/rag/documents'));
      request.files.add(http.MultipartFile.fromBytes('file', file.bytes!, filename: file.name));
      final streamed = await request.send();
      final response = await http.Response.fromStream(streamed);

      if (response.statusCode != 200) {
        throw Exception(extractErrorDetail(response));
      }

      await _loadDocuments();
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _uploading = false);
    }
  }

  Future<void> _deleteDocument(String documentId) async {
    try {
      await http.delete(Uri.parse('$apiBaseUrl/rag/documents/$documentId'));
      await _loadDocuments();
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  Future<void> _askQuestion() async {
    final question = _questionController.text.trim();
    if (question.isEmpty) {
      setState(() => _error = 'Please enter a question.');
      return;
    }

    setState(() {
      _asking = true;
      _error = null;
      _answer = null;
      _sources = [];
    });

    try {
      final response = await http.post(
        Uri.parse('$apiBaseUrl/rag/query'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'question': question}),
      );

      if (response.statusCode != 200) {
        throw Exception(extractErrorDetail(response));
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      setState(() {
        _answer = data['answer'] as String;
        _sources = (data['sources'] as List<dynamic>)
            .map((s) => RagSource.fromJson(s as Map<String, dynamic>))
            .toList();
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _asking = false);
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
              Text('Documents', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              if (_loadingDocuments)
                const Center(child: CircularProgressIndicator())
              else if (_documents.isEmpty)
                const Text('No documents uploaded yet.')
              else
                Card(
                  child: Column(
                    children: _documents
                        .map((doc) => ListTile(
                              title: Text(doc.filename),
                              subtitle: Text('${doc.chunkCount} chunk(s)'),
                              trailing: IconButton(
                                icon: const Icon(Icons.delete_outline),
                                onPressed: () => _deleteDocument(doc.documentId),
                              ),
                            ))
                        .toList(),
                  ),
                ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: _uploading ? null : _uploadDocument,
                icon: _uploading
                    ? const SizedBox(
                        height: 16,
                        width: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.upload_file),
                label: Text(_uploading ? 'Uploading...' : 'Upload document (.txt, .md, .pdf)'),
              ),
              const Divider(height: 40),
              Text('Ask a question', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              TextField(
                controller: _questionController,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Question',
                  hintText: 'Ask something about your uploaded documents...',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _asking ? null : _askQuestion,
                child: _asking
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Ask'),
              ),
              const SizedBox(height: 24),
              if (_error != null)
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              if (_answer != null) ...[
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: SelectableText(_answer!),
                  ),
                ),
                const SizedBox(height: 16),
                Text('Sources', style: Theme.of(context).textTheme.titleSmall),
                ..._sources.map(
                  (source) => Card(
                    margin: const EdgeInsets.only(top: 8),
                    child: ExpansionTile(
                      title: Text(source.filename),
                      subtitle: Text('distance: ${source.distance.toStringAsFixed(3)}'),
                      children: [
                        Padding(
                          padding: const EdgeInsets.all(16),
                          child: Text(source.text),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
