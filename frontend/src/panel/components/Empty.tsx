import { IconCanvas, IconDoc, IconShieldCheck } from './Icons'

const STARTERS = [
  { icon: <IconDoc size={17} />, title: 'ELD procedures', sub: 'Identification, placement, and forms', q: 'What does current MCPS guidance say about identifying and placing a student in ELD services?' },
  { icon: <IconShieldCheck size={17} />, title: 'Accommodations guidance', sub: 'Instruction and assessment', q: 'What does MCPS guidance say about using documented ELD accommodations during instruction and assessments?' },
  { icon: <IconDoc size={17} />, title: 'Instructional pathways', sub: 'Elementary, middle, and high school', q: 'How do MCPS ELD instructional pathways differ between elementary, middle, and high school?' },
  { icon: <IconCanvas size={17} />, title: 'Canvas courses', sub: 'Assignments and course pages', q: 'What assignments are coming up in my Canvas courses?' },
]

export function Empty({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="empty">
      <div className="empty-intro">
        <span className="eyebrow">ELD REFERENCE</span>
        <h1 className="hello">Find the guidance you need.</h1>
        <p className="sub">Search MCPS guidance and your Canvas courses. Answers include links to the material used.</p>
      </div>
      <div className="starters-label">Common questions</div>
      <div className="starters">
        {STARTERS.map((s) => (
          <button key={s.title} className="starter" onClick={() => onPick(s.q)}>
            <span className="ic">{s.icon}</span>
            <span className="starter-copy"><b>{s.title}</b><span>{s.sub}</span></span>
            <span className="starter-arrow" aria-hidden="true">→</span>
          </button>
        ))}
      </div>
    </div>
  )
}
