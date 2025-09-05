
import './App.css'
import { BrowserRouter } from 'react-router'
import Router from './routes'
import Header from './components/header'
import { Toaster } from 'sonner'

function App() {

  return (
    <>
    <BrowserRouter>
      <Header/>
      <Router/>
   </BrowserRouter>
   <Toaster
   position='top-left'
   closeButton
   
   />
    </>
  )
}

export default App
