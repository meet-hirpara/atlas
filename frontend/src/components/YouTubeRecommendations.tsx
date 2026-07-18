import { useState } from 'react'
import { Play, X } from 'lucide-react'
import type { YouTubeVideo } from '../api'

interface Props {
  videos: YouTubeVideo[]
}

function VideoModal({ video, onClose }: { video: YouTubeVideo; onClose: () => void }) {
  return (
    <div className="youtube-modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="youtube-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={`Play ${video.title}`}
      >
        <button type="button" className="youtube-modal-close" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>
        <div className="youtube-modal-embed">
          <iframe
            src={`https://www.youtube.com/embed/${video.videoId}?autoplay=1`}
            title={video.title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
        <div className="youtube-modal-meta">
          <h3 className="youtube-modal-title">{video.title}</h3>
          {video.channel ? <p className="youtube-modal-channel">{video.channel}</p> : null}
          <a
            className="youtube-modal-link"
            href={video.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open on YouTube
          </a>
        </div>
      </div>
    </div>
  )
}

export default function YouTubeRecommendations({ videos }: Props) {
  const [active, setActive] = useState<YouTubeVideo | null>(null)

  if (!videos.length) return null

  return (
    <>
      <section className="youtube-recommendations" aria-label="YouTube recommendations">
        <h3 className="youtube-recommendations-title">Recommended videos</h3>
        <div className="youtube-recommendations-row">
          {videos.map((video) => (
            <button
              key={video.videoId}
              type="button"
              className="youtube-card"
              onClick={() => setActive(video)}
              aria-label={`Play ${video.title}`}
            >
              <span className="youtube-card-thumb-wrap">
                <img
                  className="youtube-card-thumb"
                  src={video.thumbnail}
                  alt=""
                  loading="lazy"
                />
                <span className="youtube-card-play">
                  <Play size={22} fill="currentColor" />
                </span>
              </span>
              <span className="youtube-card-body">
                <span className="youtube-card-title">{video.title}</span>
                {video.channel ? (
                  <span className="youtube-card-channel">{video.channel}</span>
                ) : null}
                {video.description ? (
                  <span className="youtube-card-desc">{video.description}</span>
                ) : null}
              </span>
            </button>
          ))}
        </div>
      </section>
      {active ? <VideoModal video={active} onClose={() => setActive(null)} /> : null}
    </>
  )
}
