
import './App.css'
import { BrowserRouter } from 'react-router'
import Router from './routes'
import Header from './components/header'

function App() {

  return (
    <>
    <BrowserRouter>
      <Header/>
      <Router/>
    </BrowserRouter>
    </>
  )
}

export default App
