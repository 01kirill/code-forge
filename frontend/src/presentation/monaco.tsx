import { useEffect, useRef, useState } from 'react'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api'
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import 'monaco-editor/esm/vs/editor/contrib/suggest/browser/suggestController'
import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution'
import 'monaco-editor/esm/vs/basic-languages/csharp/csharp.contribution'
import 'monaco-editor/esm/vs/basic-languages/go/go.contribution'
import 'monaco-editor/esm/vs/basic-languages/java/java.contribution'
import 'monaco-editor/esm/vs/basic-languages/javascript/javascript.contribution'
import 'monaco-editor/esm/vs/basic-languages/pascal/pascal.contribution'
import 'monaco-editor/esm/vs/basic-languages/php/php.contribution'
import 'monaco-editor/esm/vs/basic-languages/python/python.contribution'
import 'monaco-editor/esm/vs/basic-languages/rust/rust.contribution'
import 'monaco-editor/esm/vs/basic-languages/sql/sql.contribution'
import 'monaco-editor/esm/vs/basic-languages/typescript/typescript.contribution'

import { languageSyntax, type Language } from '../domain/models'

self.MonacoEnvironment = { getWorker: () => new EditorWorker() }

const snippets = {
  python: { print: 'print(${1:value})', input: 'input()', int: 'int(${1:value})' },
  cpp: { cout: "std::cout << ${1:value} << '\\n';", cin: 'std::cin >> ${1:value};' },
}

for (const language of ['python', 'cpp'] as const) {
  monaco.languages.registerCompletionItemProvider(language, {
    provideCompletionItems(model, position) {
      const word = model.getWordUntilPosition(position)
      const range = new monaco.Range(
        position.lineNumber,
        word.startColumn,
        position.lineNumber,
        word.endColumn,
      )
      return {
        suggestions: Object.entries(snippets[language]).map(([label, insertText]) => ({
          label,
          insertText,
          range,
          kind: monaco.languages.CompletionItemKind.Snippet,
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
        })),
      }
    },
  })
}

export default function CodeEditor({
  value,
  onChange,
  language,
  label,
}: {
  value: string
  onChange: (value: string) => void
  language: Language
  label: string
}) {
  const element = useRef<HTMLDivElement>(null)
  const editor = useRef<monaco.editor.IStandaloneCodeEditor>()
  const onEdit = useRef(onChange)
  const [usePlain, setUsePlain] = useState(false)
  onEdit.current = onChange

  useEffect(() => {
    if (!element.current || usePlain) return
    let instance: monaco.editor.IStandaloneCodeEditor
    try {
      instance = monaco.editor.create(element.current, {
        automaticLayout: true,
        minimap: { enabled: false },
        ariaLabel: label,
        accessibilitySupport: 'auto',
        scrollBeyondLastLine: false,
        fontSize: 15,
        tabSize: 4,
        tabFocusMode: true,
        padding: { top: 12 },
      })
    } catch {
      setUsePlain(true)
      return
    }
    editor.current = instance
    const model = instance.getModel()
    const listener = instance.onDidChangeModelContent(() => onEdit.current(instance.getValue()))
    const applyTheme = () =>
      monaco.editor.setTheme(document.documentElement.dataset.theme === 'dark' ? 'vs-dark' : 'vs')
    const observer = new MutationObserver(applyTheme)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
    applyTheme()
    return () => {
      observer.disconnect()
      listener.dispose()
      instance.dispose()
      model?.dispose()
    }
  }, [label, usePlain])

  useEffect(() => {
    const model = editor.current?.getModel()
    if (model && model.getValue() !== value) model.setValue(value)
    const syntax = languageSyntax(language)
    if (model && model.getLanguageId() !== syntax) monaco.editor.setModelLanguage(model, syntax)
  }, [value, language, label])

  if (usePlain)
    return (
      <textarea
        className="code-input"
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  return <div className="monaco-host" ref={element} />
}
