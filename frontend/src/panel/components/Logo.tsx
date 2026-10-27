import logoUrl from '../../icons/esolv-logo.png'


export function Logo({ size = 28 }: { size?: number }) {
  return <img src={logoUrl} width={size} height={size} alt="Esolv" style={{ display: 'block', objectFit: 'contain', borderRadius: size >= 40 ? 10 : 5, background: '#fff' }} />
}
