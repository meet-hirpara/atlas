/** Active signed-in user for client-side preference scoping. */

let activeUserId: string | null = null

export function setActiveUserId(userId: string | null) {
  activeUserId = userId
}

export function getActiveUserId(): string | null {
  return activeUserId
}
