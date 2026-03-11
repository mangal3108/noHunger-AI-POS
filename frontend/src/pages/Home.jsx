import React, { useContext, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Nav from "../components/Nav";
import Card from "../components/Card";
import { dataContext } from "../context/UserContext";
import { IoClose } from "react-icons/io5";
import AddCard from "../components/AddCard";
import { useSelector, useDispatch } from "react-redux";
import { toast } from "react-toastify";
import Bill from "../components/Bill";
import { FaUtensils, FaPizzaSlice, FaHamburger, FaIceCream, FaCoffee } from "react-icons/fa";
import { GiChickenOven, GiNoodles, GiSandwich } from "react-icons/gi";
import { clearCart } from "../redux/cartSlice";
import { api, server } from "../helpers/api";
import Chatbot from "../components/Chatbot";

const Home = () => {
  const navigate = useNavigate();
  let { cate, setCate, input, showCart, setShowCart, categories, foodItems, activeCategory, setActiveCategory } = useContext(dataContext);

  const [showBill, setShowBill] = useState(false);

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 12; // 4 rows * 3 columns = 12 items

  // Reset page when category or search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [activeCategory, input]);

  // Pagination Logic
  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentItems = cate.slice(indexOfFirstItem, indexOfLastItem);
  const totalPages = Math.ceil(cate.length / itemsPerPage);

  const handlePageChange = (pageNumber) => {
    setCurrentPage(pageNumber);
  };

  // User details for order
  const [userDetails, setUserDetails] = useState({
    name: "",
    email: "",
    phone: ""
  });
  const [loading, setLoading] = useState(false);

  const dispatch = useDispatch();
  let items = useSelector((state) => state.cart);



  // Calculate totals based on new formula: (Price - Disc) + Tax
  const cartCalculation = items.reduce((acc, item) => {
    const price = parseFloat(item.price) || 0;
    const qty = parseInt(item.qty) || 1;
    const discountPercent = parseFloat(item.discount || 0);
    const taxPercent = parseFloat(item.tax || 0);

    const discountAmount = price * (discountPercent / 100);
    const priceAfterDiscount = price - discountAmount;
    const taxAmount = priceAfterDiscount * (taxPercent / 100);
    const finalPrice = priceAfterDiscount + taxAmount;

    acc.subtotal += price * qty;
    acc.discount += discountAmount * qty;
    acc.tax += taxAmount * qty;
    acc.total += finalPrice * qty;

    return acc;
  }, { subtotal: 0, discount: 0, tax: 0, total: 0 });

  let subtotal = cartCalculation.subtotal;
  let deliveryFee = 0; // 20;
  let total = cartCalculation.total + deliveryFee;

  const [checkoutOrder, setCheckoutOrder] = useState(null);

  const handlePlaceOrder = async () => {
    if (!userDetails.name || !userDetails.email || !userDetails.phone) {
      toast.error("Please fill in your details to place order.");
      return;
    }

    try {
      setLoading(true);
      const orderData = {
        user: userDetails,
        items: items.map(item => ({
          foodId: item.id,
          name: item.name,
          price: item.price,
          qty: item.qty,
          image: item.image,
          discount: item.discount,
          tax: item.tax
        })),
        totalAmount: total,
        source: 'user'
      };

      const response = await api.post('/orders', orderData);

      if (response.status === 201) {
        toast.success("Order Placed! Redirecting to Payment...");

        // Save the placed order details
        setCheckoutOrder(response.data.order);

        // Clear and redirect
        dispatch(clearCart());
        setUserDetails({ name: "", email: "", phone: "" });
        setShowCart(false);

        // Navigation to Payment Page
        navigate(`/payment/${response.data.order._id}?amount=${total}`);
      }
    } catch (error) {
      console.error(error);
      toast.error(error.response?.data?.message || "Failed to place order.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-50 w-full h-screen flex flex-col md:flex-row overflow-hidden relative">

      {/* LEFT SIDE - CATEGORIES (Desktop Sidebar / Mobile Top Bar) */}
      <div className={`
                w-full md:w-[260px] md:h-full bg-white border-b md:border-b-0 md:border-r border-gray-200 
                flex md:flex-col gap-4 p-4 md:p-6 overflow-x-auto md:overflow-y-auto shrink-0 z-20 
                ${input ? 'hidden md:flex' : 'flex'}
            `}>
        <div className="hidden md:flex items-center gap-3 mb-6 px-2">
          <div className="w-8 h-8 rounded-full bg-orange-500 text-white flex items-center justify-center">
            <FaUtensils size={14} />
          </div>
          <span className="font-bold font-heading text-gray-800 text-lg">Menu</span>
        </div>

        <div className="flex md:flex-col gap-3 min-w-max md:min-w-0">

          <div
            className={`
                px-4 py-3 md:py-4 rounded-xl flex md:flex-row items-center gap-3 cursor-pointer transition-all duration-200 group
                ${activeCategory === "All" ? 'bg-green-600 text-white shadow-lg shadow-green-200 scale-105' : 'bg-gray-50 hover:bg-green-50 text-gray-600 hover:text-green-700'}
            `}
            onClick={() => setActiveCategory("All")}
          >
            <div className={`w-8 h-8 rounded-md flex items-center justify-center overflow-hidden ${activeCategory === "All" ? 'ring-2 ring-white/30 bg-white' : 'bg-white shadow-sm'}`}>
              <FaUtensils size={14} className={activeCategory === "All" ? "text-green-600" : "text-gray-400"} />
            </div>
            <span className="font-semibold font-heading text-sm whitespace-nowrap capitalize">All</span>
          </div>

          {categories.map((item) => {
            return (
              <div
                key={item._id}
                className={`
                                  px-4 py-3 md:py-4 rounded-xl flex md:flex-row items-center gap-3 cursor-pointer transition-all duration-200 group
                                  ${activeCategory === item.name ? 'bg-green-600 text-white shadow-lg shadow-green-200 scale-105' : 'bg-gray-50 hover:bg-green-50 text-gray-600 hover:text-green-700'}
                              `}
                onClick={() => setActiveCategory(item.name)}
              >
                <div className={`w-8 h-8 rounded-md flex items-center justify-center overflow-hidden ${activeCategory === item.name ? 'ring-2 ring-white/30' : 'bg-white shadow-sm'}`}>
                  <img src={item.image ? `${server}/${item.image}` : "https://placehold.co/100?text=Cat"} alt={item.name} className="w-full h-full object-cover" />
                </div>
                <span className="font-semibold font-heading text-sm whitespace-nowrap capitalize">{item.name}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* RIGHT SIDE - MAIN CONTENT */}
      <div className="flex-1 h-full flex flex-col relative">
        <Nav />

        {/* Scrollable Content Area */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 pb-32 md:pb-10 scroll-smooth">

          {/* Welcome Banner */}
          {!input && (
            <div className="w-full h-[150px] md:h-[180px] rounded-2xl bg-gradient-to-r from-green-600 to-emerald-500 mb-8 flex items-center px-8 md:px-12 shadow-xl relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-12 translate-x-12"></div>
              <div className="relative z-10 text-white">
                <h1 className="text-2xl md:text-4xl font-bold font-heading mb-2 tracking-tight">Delicious Food, <br /> Delivered To You</h1>
                <p className="text-green-100 text-sm md:text-base opacity-90">Choose from out best menu items.</p>
              </div>
            </div>
          )}

          {/* Food Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-10 md:gap-12 justify-items-center">
            {currentItems.length > 0 ? (
              currentItems.map((item) => (
                <Card
                  key={item._id}
                  name={item.name}
                  image={item.image}
                  price={item.price}
                  type={item.description} // Assuming description is what we want to show, or maybe category name?
                  id={item._id}
                  discount={item.discount}
                  tax={item.tax}
                />
              ))
            ) : (
              <div className="col-span-full h-64 flex flex-col items-center justify-center text-gray-400">
                <span className="text-6xl mb-4">🍽️</span>
                <h3 className="text-xl font-semibold font-heading">No Dish Found</h3>
                <p>Try searching for something else.</p>
              </div>
            )}
          </div>

          {/* Pagination Controls */}
          {cate.length > itemsPerPage && (
            <div className="flex justify-center items-center mt-12 gap-4">
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                className={`
                  px-4 py-2 rounded-lg border font-medium transition-colors
                  ${currentPage === 1
                    ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:text-green-600'}
                `}
              >
                Previous
              </button>

              <div className="flex items-center gap-2">
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((number) => (
                  <button
                    key={number}
                    onClick={() => handlePageChange(number)}
                    className={`
                      w-10 h-10 rounded-lg flex items-center justify-center font-bold transition-all
                      ${currentPage === number
                        ? 'bg-green-600 text-white shadow-lg shadow-green-200 scale-105'
                        : 'bg-white text-gray-600 border border-gray-200 hover:border-green-500 hover:text-green-600'}
                    `}
                  >
                    {number}
                  </button>
                ))}
              </div>

              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                className={`
                  px-4 py-2 rounded-lg border font-medium transition-colors
                  ${currentPage === totalPages
                    ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:text-green-600'}
                `}
              >
                Next
              </button>
            </div>
          )}
        </div>
      </div>

      {/* CART SIDEBAR */}
      <div
        className={`
                  fixed right-0 top-0 h-full w-full md:w-[400px] bg-white shadow-2xl z-50 transform transition-transform duration-300 ease-in-out
                  flex flex-col
                  ${showCart ? "translate-x-0" : "translate-x-full"}
              `}
      >
        {/* 1. Header (Fixed) */}
        <header className="p-4 border-b border-gray-100 flex justify-between items-center bg-white z-10 shrink-0">
          <div>
            <h2 className="text-xl font-bold font-heading text-gray-800">Your Order</h2>
            <span className="text-sm text-gray-500">{items.length} items</span>
          </div>
          <button
            onClick={() => setShowCart(false)}
            className="w-8 h-8 rounded-full bg-gray-50 hover:bg-red-50 text-gray-400 hover:text-red-500 flex items-center justify-center transition-colors"
          >
            <IoClose size={20} />
          </button>
        </header>

        {/* 2. Scrollable Content (Items + Details + Summary) */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth">

          {/* Order Items List */}
          <div className="space-y-3">
            {items.length > 0 ? (
              items.map((item) => (
                <AddCard
                  key={item.id}
                  name={item.name}
                  price={item.price}
                  id={item.id}
                  image={item.image}
                  qty={item.qty}
                  discount={item.discount}
                  tax={item.tax}
                />
              ))
            ) : (
              <div className="flex flex-col items-center justify-center text-center space-y-4 py-10 opacity-60">
                <div className="text-6xl">🛒</div>
                <p className="text-gray-500 font-medium">Your cart is empty</p>
                <button
                  onClick={() => setShowCart(false)}
                  className="text-green-600 font-semibold hover:underline"
                >
                  Start Shopping
                </button>
              </div>
            )}
          </div>

          {items.length > 0 && (
            <>
              {/* Divider */}
              <div className="h-px bg-gray-100 my-2"></div>

              {/* Customer Details Form */}
              <div className="space-y-3">
                <h3 className="text-md font-bold text-gray-700 flex items-center gap-2">
                  <span className="w-1 h-4 bg-green-500 rounded-full"></span>
                  Customer Details
                </h3>
                <div className="space-y-2">
                  <input
                    type="text"
                    placeholder="Full Name"
                    className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-green-500 focus:bg-white transition-colors"
                    value={userDetails.name}
                    onChange={(e) => setUserDetails({ ...userDetails, name: e.target.value })}
                  />
                  <input
                    type="email"
                    placeholder="Email Address"
                    className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-green-500 focus:bg-white transition-colors"
                    value={userDetails.email}
                    onChange={(e) => setUserDetails({ ...userDetails, email: e.target.value })}
                  />
                  <input
                    type="tel"
                    placeholder="Phone Number"
                    className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-green-500 focus:bg-white transition-colors"
                    value={userDetails.phone}
                    onChange={(e) => setUserDetails({ ...userDetails, phone: e.target.value })}
                  />
                </div>
              </div>

              {/* Divider */}
              <div className="h-px bg-gray-100 my-2"></div>

              {/* Bill Summary */}
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <h3 className="text-md font-bold text-gray-700 flex items-center gap-2">
                    <span className="w-1 h-4 bg-orange-500 rounded-full"></span>
                    Bill Summary
                  </h3>
                  <button
                    onClick={() => setShowBill(true)}
                    className="text-xs text-blue-600 font-semibold hover:underline"
                  >
                    View Receipt
                  </button>
                </div>
                <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm text-gray-600">
                  <div className="flex justify-between">
                    <span>Total</span>
                    <span className="font-medium">₹ {subtotal.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-red-500">
                    <span>Discount</span>
                    <span className="font-medium">- ₹ {cartCalculation.discount.toFixed(2)}</span>
                  </div>

                  <div className="h-px bg-gray-200 border-dashed my-1"></div>

                  <div className="flex justify-between font-semibold text-gray-700">
                    <span>Subtotal</span>
                    <span>₹ {(subtotal - cartCalculation.discount).toFixed(2)}</span>
                  </div>

                  <div className="flex justify-between">
                    <span>Tax</span>
                    <span className="font-medium">₹ {cartCalculation.tax.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between hidden">
                    <span>Delivery Fee</span>
                    <span className="font-medium">₹ {deliveryFee}</span>
                  </div>
                  <div className="h-px bg-gray-200 my-1"></div>
                  <div className="flex justify-between text-base font-bold text-gray-800">
                    <span>You Pay</span>
                    <span>₹ {(subtotal - cartCalculation.discount + cartCalculation.tax).toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Extra padding for scrolling ensuring content isn't hidden behind footer if we didn't use flex-col properly, but flex-col handles it. Added padding-bottom just in case. */}
          <div className="pb-2"></div>
        </div>

        {/* 3. Footer (Fixed Buttons) */}
        {items.length > 0 && (
          <div className="p-4 border-t border-gray-100 bg-white shrink-0 space-y-3 z-10">
            <div className="grid grid-cols-2 gap-3">
              <button
                className="py-3 rounded-xl border border-gray-200 text-gray-600 font-semibold text-sm hover:bg-gray-50 transition-colors"
                onClick={() => setShowCart(false)}
              >
                Cancel
              </button>
              <button
                className="py-3 rounded-xl border border-red-100 text-red-500 font-semibold text-sm hover:bg-red-50 transition-colors"
                onClick={() => dispatch(clearCart())}
              >
                Clear Cart
              </button>
            </div>
            <button
              className="w-full py-3 rounded-xl bg-green-600 text-white font-bold text-lg shadow-lg shadow-green-100 hover:bg-green-700 hover:shadow-green-200 transition-all transform hover:-translate-y-0.5 active:translate-y-0"
              onClick={handlePlaceOrder}
              disabled={loading}
            >
              {loading ? 'Processing...' : `Place Order  •  ₹${total}`}
            </button>
          </div>
        )}
      </div>

      {/* Bill Modal */}
      {showBill && (
        <Bill
          items={checkoutOrder ? checkoutOrder.items : items}
          customerDetails={checkoutOrder ? checkoutOrder.user : userDetails}
          orderDate={checkoutOrder ? checkoutOrder.createdAt : null}
          deliveryFee={deliveryFee}
          onClose={() => {
            setShowBill(false);
            // Optional: reset checkoutOrder if you want only one-time view after success, 
            // but keeping it until next action is fine too. 
            // Better to reset it when closing if we want "View Receipt" to work for new cart items immediately.
            setCheckoutOrder(null);
          }}
        />
      )}

      {/* Chatbot Widget */}
      <Chatbot />
    </div>
  );
};

export default Home;
