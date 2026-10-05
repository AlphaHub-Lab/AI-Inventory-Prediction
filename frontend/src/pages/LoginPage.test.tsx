import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import LoginPage from './LoginPage'

describe('LoginPage', () => {
  it('shows an empty sign-in form without prefilled credentials', () => {
    render(<LoginPage onLogin={() => undefined} />)
    expect(screen.getByRole('button', { name: /sign in securely/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/work email/i)).toHaveValue('')
  })
})
