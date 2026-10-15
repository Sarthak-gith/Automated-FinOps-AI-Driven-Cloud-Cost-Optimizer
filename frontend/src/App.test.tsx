import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

describe('application shell',()=>{
  beforeEach(()=>localStorage.clear())
  afterEach(()=>cleanup())
  it('shows the demo sign-in screen when no session exists',()=>{
    render(<BrowserRouter><App/></BrowserRouter>)
    expect(screen.getByRole('heading',{name:'Welcome back'})).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveValue('admin@finops.local')
  })
})
