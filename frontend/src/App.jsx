import React, { useContext } from 'react'
import Home from './pages/Home'
import AddCategory from './pages/AddCategory'
import AdminLogin from './pages/AdminLogin'
import AdminDashboard from './pages/AdminDashboard'
import AdminCategory from './pages/AdminCategory'
import AdminItem from './pages/AdminItem'
import AddItem from './pages/AddItem'
import EditItem from './pages/EditItem'
import AdminBill from './pages/AdminBill'
import AdminUserDetails from './pages/AdminUserDetails'
import Payment from './pages/Payment'
import { Routes, Route } from 'react-router-dom'
import { ToastContainer } from 'react-toastify'

import ProtectedAdminRoute from './components/ProtectedAdminRoute'

const App = () => {

  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/payment/:orderId" element={<Payment />} />
        <Route path="/admin/add-category" element={<ProtectedAdminRoute><AddCategory /></ProtectedAdminRoute>} />
        <Route path="/admin-secret-login" element={<AdminLogin />} />
        <Route path="/admin/dashboard" element={<ProtectedAdminRoute><AdminDashboard /></ProtectedAdminRoute>} />
        <Route path="/admin/category" element={<ProtectedAdminRoute><AdminCategory /></ProtectedAdminRoute>} />
        <Route path="/admin/item" element={<ProtectedAdminRoute><AdminItem /></ProtectedAdminRoute>} />
        <Route path="/admin/add-item" element={<ProtectedAdminRoute><AddItem /></ProtectedAdminRoute>} />
        <Route path="/admin/edit-item/:id" element={<ProtectedAdminRoute><EditItem /></ProtectedAdminRoute>} />
        <Route path="/admin/bill" element={<ProtectedAdminRoute><AdminBill /></ProtectedAdminRoute>} />
        <Route path="/admin/userDetails" element={<ProtectedAdminRoute><AdminUserDetails /></ProtectedAdminRoute>} />
      </Routes>
      <ToastContainer />
    </>
  )
}

export default App