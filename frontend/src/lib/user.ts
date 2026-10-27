import type { User } from './types'

export function displayName(user: User): string {
  return user.name.trim() || 'Your account'
}
