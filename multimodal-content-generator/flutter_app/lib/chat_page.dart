import 'dart:convert';
import 'dart:typed_data';

import 'package:desktop_drop/desktop_drop.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'api_config.dart';

const _supportedExtensions = ['txt', 'md', 'pdf'];

class ChatSource {
  final String filename;
  final String text;
  final double distance;

  ChatSource({required this.filename, required this.text, required this.distance});

  factory ChatSource.fromJson(Map<String, dynamic> json) => ChatSource(
        filename: json['filename'] as String,
        text: json['text'] as String,
        distance: (json['distance'] as num).toDouble(),
      );
}

/// role is 'user', 'model', or the client-only 'system' (upload notices -
/// never sent to or persisted by the backend, just a UI cue).
class ChatMessage {
  final String role;
  final String? text;
  final Uint8List? imageBytes;
  final List<ChatSource> sources;

  ChatMessage({required this.role, this.text, this.imageBytes, this.sources = const []});

  bool get isUser => role == 'user';
  bool get isSystem => role == 'system';

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        role: json['role'] as String,
        text: json['text'] as String?,
        imageBytes: json['image_base64'] != null ? base64Decode(json['image_base64'] as String) : null,
        sources: (json['sources'] as List<dynamic>? ?? [])
            .map((s) => ChatSource.fromJson(s as Map<String, dynamic>))
            .toList(),
      );
}

class ConversationSummary {
  final String conversationId;
  final String title;

  ConversationSummary({required this.conversationId, required this.title});

  factory ConversationSummary.fromJson(Map<String, dynamic> json) => ConversationSummary(
        conversationId: json['conversation_id'] as String,
        title: json['title'] as String,
      );
}

class ChatPage extends StatefulWidget {
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeModeChanged;

  const ChatPage({super.key, required this.themeMode, required this.onThemeModeChanged});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();

  List<ConversationSummary> _conversations = [];
  String? _conversationId;
  List<ChatMessage> _messages = [];
  bool _sending = false;
  bool _uploading = false;
  bool _dragging = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadConversations();
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadConversations() async {
    try {
      final response = await http.get(Uri.parse('$apiBaseUrl/chat/conversations'));
      final data = jsonDecode(response.body) as List<dynamic>;
      setState(() {
        _conversations = data.map((c) => ConversationSummary.fromJson(c as Map<String, dynamic>)).toList();
      });
    } catch (e) {
      setState(() => _error = 'Could not load conversations: $e');
    }
  }

  Future<void> _openConversation(String conversationId) async {
    try {
      final response = await http.get(Uri.parse('$apiBaseUrl/chat/conversations/$conversationId'));
      if (response.statusCode != 200) throw Exception(extractErrorDetail(response));

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      setState(() {
        _conversationId = conversationId;
        _messages = (data['messages'] as List<dynamic>)
            .map((m) => ChatMessage.fromJson(m as Map<String, dynamic>))
            .toList();
        _error = null;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  static const _themeModeCycle = [ThemeMode.system, ThemeMode.light, ThemeMode.dark];

  void _cycleThemeMode() {
    final next = _themeModeCycle[(_themeModeCycle.indexOf(widget.themeMode) + 1) % _themeModeCycle.length];
    widget.onThemeModeChanged(next);
  }

  IconData _themeModeIcon(ThemeMode mode) => switch (mode) {
        ThemeMode.system => Icons.brightness_auto,
        ThemeMode.light => Icons.light_mode,
        ThemeMode.dark => Icons.dark_mode,
      };

  String _themeModeLabel(ThemeMode mode) => switch (mode) {
        ThemeMode.system => 'System',
        ThemeMode.light => 'Light',
        ThemeMode.dark => 'Dark',
      };

  void _startNewChat() {
    setState(() {
      _conversationId = null;
      _messages = [];
      _error = null;
    });
  }

  Future<void> _deleteConversation(String conversationId) async {
    try {
      await http.delete(Uri.parse('$apiBaseUrl/chat/conversations/$conversationId'));
      if (_conversationId == conversationId) _startNewChat();
      await _loadConversations();
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    });
  }

  bool _isSupported(String filename) {
    final ext = filename.split('.').last.toLowerCase();
    return _supportedExtensions.contains(ext);
  }

  Future<void> _uploadBytes(String filename, Uint8List bytes) async {
    if (!_isSupported(filename)) {
      setState(() {
        _error = '$filename is not a supported type. Use one of: .txt, .md, .pdf';
      });
      return;
    }

    setState(() {
      _uploading = true;
      _error = null;
    });

    try {
      final request = http.MultipartRequest('POST', Uri.parse('$apiBaseUrl/rag/documents'));
      request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
      final streamed = await request.send();
      final response = await http.Response.fromStream(streamed);

      if (response.statusCode != 200) {
        throw Exception(extractErrorDetail(response));
      }

      setState(() {
        _messages = [
          ..._messages,
          ChatMessage(role: 'system', text: 'Attached $filename - ask me anything about it.'),
        ];
      });
      _scrollToBottom();
    } catch (e) {
      setState(() => _error = 'Could not upload $filename: $e');
    } finally {
      setState(() => _uploading = false);
    }
  }

  Future<void> _pickAndUploadFile() async {
    final picked = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: _supportedExtensions,
      withData: true,
      allowMultiple: true,
    );
    if (picked == null) return;

    for (final file in picked.files) {
      if (file.bytes != null) {
        await _uploadBytes(file.name, file.bytes!);
      }
    }
  }

  Future<void> _handleDrop(DropDoneDetails details) async {
    setState(() => _dragging = false);
    for (final file in details.files) {
      final bytes = await file.readAsBytes();
      await _uploadBytes(file.name, bytes);
    }
  }

  Future<void> _sendMessage() async {
    final text = _inputController.text.trim();
    if (text.isEmpty || _sending) return;

    setState(() {
      _sending = true;
      _error = null;
      _messages = [..._messages, ChatMessage(role: 'user', text: text)];
      _inputController.clear();
    });
    _scrollToBottom();

    try {
      var conversationId = _conversationId;
      if (conversationId == null) {
        final createResponse = await http.post(Uri.parse('$apiBaseUrl/chat/conversations'));
        if (createResponse.statusCode != 200) throw Exception(extractErrorDetail(createResponse));
        conversationId = (jsonDecode(createResponse.body) as Map<String, dynamic>)['conversation_id'] as String;
        setState(() => _conversationId = conversationId);
      }

      final response = await http.post(
        Uri.parse('$apiBaseUrl/chat/conversations/$conversationId/messages'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'message': text}),
      );
      if (response.statusCode != 200) throw Exception(extractErrorDetail(response));

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      setState(() {
        _messages = [..._messages, ChatMessage.fromJson(data['message'] as Map<String, dynamic>)];
      });
      _scrollToBottom();
      await _loadConversations();
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      drawer: _buildDrawer(context),
      appBar: AppBar(
        title: const Text('Chat'),
        actions: [
          IconButton(
            icon: Icon(_themeModeIcon(widget.themeMode)),
            tooltip: 'Theme: ${_themeModeLabel(widget.themeMode)}',
            onPressed: _cycleThemeMode,
          ),
          IconButton(
            icon: const Icon(Icons.add_comment_outlined),
            tooltip: 'New chat',
            onPressed: _startNewChat,
          ),
        ],
      ),
      body: DropTarget(
        onDragEntered: (_) => setState(() => _dragging = true),
        onDragExited: (_) => setState(() => _dragging = false),
        onDragDone: _handleDrop,
        child: Stack(
          children: [
            Column(
              children: [
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  ),
                Expanded(
                  child: _messages.isEmpty
                      ? const Center(
                          child: Text(
                            'Ask anything - I can chat, search documents you drop in, or generate images.',
                            textAlign: TextAlign.center,
                          ),
                        )
                      : ListView.builder(
                          controller: _scrollController,
                          padding: const EdgeInsets.all(16),
                          itemCount: _messages.length,
                          itemBuilder: (context, index) => _MessageBubble(message: _messages[index]),
                        ),
                ),
                if (_sending || _uploading) const LinearProgressIndicator(),
                SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        IconButton(
                          icon: const Icon(Icons.attach_file),
                          tooltip: 'Attach a document',
                          onPressed: _uploading ? null : _pickAndUploadFile,
                        ),
                        Expanded(
                          child: TextField(
                            controller: _inputController,
                            minLines: 1,
                            maxLines: 5,
                            decoration: const InputDecoration(
                              hintText: 'Message, or drop a file...',
                              border: OutlineInputBorder(),
                              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                            ),
                            onSubmitted: (_) => _sendMessage(),
                          ),
                        ),
                        const SizedBox(width: 8),
                        IconButton.filled(
                          onPressed: _sending ? null : _sendMessage,
                          icon: const Icon(Icons.send),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
            if (_dragging)
              Positioned.fill(
                child: Container(
                  color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
                  child: Center(
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.surface,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Theme.of(context).colorScheme.primary, width: 2),
                      ),
                      child: const Text('Drop to upload (.txt, .md, .pdf)'),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildDrawer(BuildContext context) {
    return Drawer(
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text('Conversations', style: Theme.of(context).textTheme.titleMedium),
            ),
            Expanded(
              child: _conversations.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.all(16),
                      child: Text('No conversations yet.'),
                    )
                  : ListView(
                      children: _conversations
                          .map((c) => ListTile(
                                title: Text(c.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                                selected: c.conversationId == _conversationId,
                                onTap: () {
                                  Navigator.of(context).pop();
                                  _openConversation(c.conversationId);
                                },
                                trailing: IconButton(
                                  icon: const Icon(Icons.delete_outline),
                                  onPressed: () => _deleteConversation(c.conversationId),
                                ),
                              ))
                          .toList(),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final ChatMessage message;

  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    if (message.isSystem) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Chip(
            avatar: const Icon(Icons.attach_file, size: 16),
            label: Text(message.text ?? ''),
            visualDensity: VisualDensity.compact,
          ),
        ),
      );
    }

    final colorScheme = Theme.of(context).colorScheme;
    final isUser = message.isUser;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
        child: Card(
          color: isUser ? colorScheme.primaryContainer : colorScheme.surfaceContainerHighest,
          margin: const EdgeInsets.symmetric(vertical: 6),
          clipBehavior: Clip.antiAlias,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (message.imageBytes != null) ...[
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.memory(message.imageBytes!),
                  ),
                  if (message.text != null) const SizedBox(height: 8),
                ],
                if (message.text != null) SelectableText(message.text!),
                if (message.sources.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: message.sources
                        .map((s) => Chip(
                              label: Text(s.filename, style: const TextStyle(fontSize: 11)),
                              visualDensity: VisualDensity.compact,
                            ))
                        .toList(),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
