import { useMemo, useState } from 'react'
import { Check, Copy, Download, FileCode, FolderOpen } from 'lucide-react'
import {
  buildFileTree,
  downloadProjectZip,
  type ProjectFile,
} from '../utils/projectFiles'
import CodeBlock from './CodeBlock'

interface Props {
  files: ProjectFile[]
}

export default function ProjectFilesPanel({ files }: Props) {
  const [activePath, setActivePath] = useState(files[0]?.path ?? '')
  const [copiedAll, setCopiedAll] = useState(false)

  const tree = useMemo(() => buildFileTree(files.map((f) => f.path)), [files])
  const activeFile = files.find((f) => f.path === activePath) ?? files[0]
  const dirs = useMemo(() => Array.from(tree.keys()).sort(), [tree])

  const handleCopyAll = async () => {
    const bundle = files.map((f) => `// ${f.path}\n${f.content}`).join('\n\n')
    try {
      await navigator.clipboard.writeText(bundle)
      setCopiedAll(true)
      setTimeout(() => setCopiedAll(false), 2000)
    } catch {
      // ignore
    }
  }

  const handleDownload = () => {
    const name = files[0]?.path.split('/')[0] ?? 'project'
    downloadProjectZip(files, name)
  }

  return (
    <div className="project-files-panel">
      <div className="project-files-header">
        <div className="project-files-title">
          <FolderOpen size={16} />
          <span>Project files ({files.length})</span>
        </div>
        <div className="project-files-actions">
          <button type="button" className="project-files-btn" onClick={handleCopyAll}>
            {copiedAll ? <Check size={14} /> : <Copy size={14} />}
            <span>{copiedAll ? 'Copied' : 'Copy all'}</span>
          </button>
          <button type="button" className="project-files-btn" onClick={handleDownload}>
            <Download size={14} />
            <span>Download ZIP</span>
          </button>
        </div>
      </div>

      <div className="project-files-body">
        <nav className="project-files-tree" aria-label="Project file tree">
          {dirs.map((dir) => (
            <div key={dir || '__root'} className="project-files-dir">
              {dir ? <div className="project-files-dir-label">{dir}/</div> : null}
              <ul>
                {(tree.get(dir) ?? []).map((name) => {
                  const path = dir ? `${dir}/${name}` : name
                  const isActive = path === activeFile?.path
                  return (
                    <li key={path}>
                      <button
                        type="button"
                        className={`project-files-file${isActive ? ' active' : ''}`}
                        onClick={() => setActivePath(path)}
                      >
                        <FileCode size={13} />
                        <span>{name}</span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </nav>

        {activeFile ? (
          <div className="project-files-preview">
            <CodeBlock
              code={activeFile.content}
              language={activeFile.language}
              filePath={activeFile.path}
            />
          </div>
        ) : null}
      </div>
    </div>
  )
}
