// Copyright cocotb contributors
// Licensed under the Revised BSD License, see LICENSE for details.
// SPDX-License-Identifier: BSD-3-Clause

#pragma once

#include <gpi.h>

#include <coroutine>
#include <cstdint>
#include <deque>
#include <iostream>
#include <optional>
#include <string>
#include <cstdlib>
#include <type_traits>
#include <utility>
#include <vector>

#include <iomanip>
#include <mutex>
#include <cmath>

namespace cocotb {

class Scheduler;  // forward declaration

class Handle {
public:
    Handle() = default;
    explicit Handle(gpi_sim_hdl handle) : handle_(handle) {}

    Handle operator[](const std::string &name) const {
        // std::cout << "Get Handle[" << name << "]" << std::endl;
        if (!handle_) {
            std::cerr << "Attempted to index an invalid handle with '" << name
                      << "'" << std::endl;
            return Handle{};
        }
        Handle child(gpi_get_handle_by_name(handle_, name.c_str(), GPI_AUTO));
        if (!child.valid()) {
            std::cerr << "Failed to find child '" << name << "'" << std::endl;
        }
        return child;
    }

    Handle &operator=(int32_t value);

    template <typename T>
    T value() const {
        if (!handle_) {
            std::cerr << "Attempted to read an invalid handle" << std::endl;
            return T{};
        }
        if constexpr (std::is_same_v<T, double>) {
            return static_cast<double>(gpi_get_signal_value_real(handle_));
        } else {
            return static_cast<T>(gpi_get_signal_value_long(handle_));
        }
    }

    bool valid() const { return handle_ != nullptr; }
    gpi_sim_hdl raw() const { return handle_; }

private:
    gpi_sim_hdl handle_{nullptr};
};

class Dut : public Handle {
public:
    Dut() = default;
    explicit Dut(gpi_sim_hdl handle) : Handle(handle) {}
};
// using Dut = Handle;

template <typename T = void>
class task {
public:
    struct promise_type {
        bool detached{false};
        bool completed{false};
        bool cancelled{false};
        std::coroutine_handle<> join_waiter{};

        task<T> get_return_object() {
            return task<T>{std::coroutine_handle<promise_type>::from_promise(
                *this)};
        }
        std::suspend_always initial_suspend() const noexcept { return {}; }
        std::suspend_always final_suspend() const noexcept { return {}; }
        void return_void() const noexcept {}
        void unhandled_exception() const { std::terminate(); }
    };

    using handle_type = std::coroutine_handle<promise_type>;

    explicit task(handle_type handle) : coro_(handle) {}
    task(task &&other) noexcept : coro_(other.coro_) { other.coro_ = {}; }
    task &operator=(task &&other) noexcept {
        if (this != &other) {
            if (coro_) {
                coro_.destroy();
            }
            coro_ = other.coro_;
            other.coro_ = {};
        }
        return *this;
    }
    task(const task &) = delete;
    task &operator=(const task &) = delete;

    ~task() {
        if (coro_) {
            coro_.destroy();
        }
    }

    handle_type release() {
        auto handle = coro_;
        coro_ = {};
        return handle;
    }

    void detach() {
        if (coro_) {
            coro_.promise().detached = true;
        }
    }

    bool done() const { return coro_ && coro_.done(); }

    handle_type handle() const { return coro_; }

    struct join_awaiter {
        handle_type handle;
        bool await_ready() const noexcept {
            return !handle || handle.promise().completed;
        }
        void await_suspend(std::coroutine_handle<> cont) const noexcept {
            handle.promise().join_waiter = cont;
        }
        void await_resume() const noexcept {
            if (handle) {
                handle.destroy();
            }
        }
    };

    join_awaiter join() const { return join_awaiter{coro_}; }

private:
    handle_type coro_;
};

using test_fn = task<> (*)(Dut &);

class Scheduler {
public:
    static Scheduler &instance();

    void set_dut_handle(gpi_sim_hdl handle);
    void register_test(const std::string &name, test_fn fn);
    void start_all_tests();

    void schedule_task(task<> &&t);
    void schedule_handle(task<>::handle_type handle);
    void schedule_after_time(std::coroutine_handle<> handle, uint64_t delay);
    void schedule_on_edge(std::coroutine_handle<> handle, gpi_sim_hdl signal,
                          gpi_edge edge);
    void enqueue_ready(std::coroutine_handle<> handle);
    void schedule_readwrite(task<>::handle_type handle);
    void schedule_readonly(task<>::handle_type handle);
    void request_readwrite_callback();
    void run_ready(bool flush_writes = true);
    void run_next_test();
    void queue_write(gpi_sim_hdl handle, int32_t value);

private:
    using TaskHandle = task<>::handle_type;
    struct WriteRequest {
        gpi_sim_hdl handle{nullptr};
        int32_t value{0};
    };

    struct BaseCallback {
        Scheduler *sched{nullptr};
        TaskHandle coro;
        gpi_cb_hdl cb_handle{nullptr};
    };

    struct EdgeCallback : BaseCallback {
        gpi_sim_hdl signal{nullptr};
        gpi_edge edge{GPI_VALUE_CHANGE};
    };

    static int timer_callback(void *userdata);
    static int edge_callback(void *userdata);
    static int readwrite_callback(void *userdata);
    static int readonly_callback(void *userdata);
    static int nexttime_rw_callback(void *userdata);

    std::deque<TaskHandle> ready_;
    std::deque<WriteRequest> pending_writes_;
    bool rw_cb_pending_{false};
    bool in_readonly_{false};
    bool need_rw_after_ro_{false};
    std::vector<std::pair<std::string, test_fn>> tests_;
    std::optional<Dut> dut_;
    gpi_sim_hdl dut_handle_{nullptr};
    size_t next_test_index_{0};
};

class Timer {
public:
    explicit Timer(uint64_t delay) : delay_(delay) {}
    bool await_ready() const noexcept { return delay_ == 0; }
    void await_suspend(std::coroutine_handle<> handle) const {
        Scheduler::instance().schedule_after_time(handle, delay_);
    }
    void await_resume() const noexcept {}

private:
    uint64_t delay_;
};

class RisingEdge {
public:
    explicit RisingEdge(Handle signal) : signal_(signal) {}
    bool await_ready() const noexcept { return false; }
    void await_suspend(std::coroutine_handle<> handle) const {
        Scheduler::instance().schedule_on_edge(handle, signal_.raw(), GPI_RISING);
    }
    void await_resume() const noexcept {}

private:
    Handle signal_;
};

inline Scheduler &Scheduler::instance() {
    static Scheduler sched;
    return sched;
}

inline void Scheduler::set_dut_handle(gpi_sim_hdl handle) {
    dut_handle_ = handle;
    dut_.reset();
}

inline void Scheduler::register_test(const std::string &name, test_fn fn) {
    tests_.push_back({name, fn});
}

inline void Scheduler::start_all_tests() {
    if (!dut_handle_) {
        std::cerr << "No DUT handle available" << std::endl;
        return;
    }

    dut_.emplace(dut_handle_);
    next_test_index_ = 0;
    run_next_test();
}

inline void Scheduler::schedule_task(task<> &&t) {
    auto handle = t.release();
    if (handle) {
        ready_.push_back(handle);
    }
}

inline void Scheduler::schedule_handle(task<>::handle_type handle) {
    if (handle) {
        ready_.push_back(handle);
    }
}

inline void Scheduler::enqueue_ready(std::coroutine_handle<> handle) {
    if (!handle) {
        return;
    }
    ready_.push_back(
        TaskHandle::from_address(const_cast<void *>(handle.address())));
    request_readwrite_callback();
}

inline void Scheduler::schedule_readwrite(TaskHandle handle) {
    if (!handle) {
        return;
    }
    ready_.push_back(handle);
    request_readwrite_callback();
}

inline void Scheduler::schedule_readonly(TaskHandle handle) {
    if (!handle) {
        return;
    }
    ready_.push_back(handle);
    gpi_register_readonly_callback(&Scheduler::readonly_callback, this);
}

inline void Scheduler::request_readwrite_callback() {
    if (in_readonly_) {
        need_rw_after_ro_ = true;
        return;
    }
    if (rw_cb_pending_) {
        return;
    }
    rw_cb_pending_ = true;
    gpi_register_readwrite_callback(&Scheduler::readwrite_callback, this);
}

inline void Scheduler::queue_write(gpi_sim_hdl handle, int32_t value) {
    pending_writes_.push_back(WriteRequest{handle, value});
    request_readwrite_callback();
}

inline void Scheduler::run_ready(bool flush_writes) {
    if (flush_writes) {
        while (!pending_writes_.empty()) {
            auto wr = pending_writes_.front();
            pending_writes_.pop_front();
            gpi_set_signal_value_int(wr.handle, wr.value, GPI_DEPOSIT);
        }
        rw_cb_pending_ = false;
    }
    while (!ready_.empty()) {
        auto handle = ready_.front();
        ready_.pop_front();
        if (!handle) {
            continue;
        }
        if (handle.promise().cancelled) {
            handle.destroy();
            continue;
        }
        handle.resume();
        if (handle.done()) {
            auto &promise = handle.promise();
            promise.completed = true;
            if (promise.join_waiter) {
                enqueue_ready(promise.join_waiter);
            }
            if (promise.detached) {
                handle.destroy();
            }
            if (promise.detached) {
                run_next_test();
            }
        }
    }
}

inline int Scheduler::timer_callback(void *userdata) {
    auto *cb = static_cast<BaseCallback *>(userdata);
    cb->sched->schedule_readwrite(cb->coro);
    delete cb;
    return 0;
}

inline int Scheduler::edge_callback(void *userdata) {
    // std::cout << "Edge callback" << std::endl;
    auto *cb = static_cast<EdgeCallback *>(userdata);
    cb->sched->ready_.push_back(cb->coro);
    cb->sched->run_ready(false);
    delete cb;
    return 0;
}

inline int Scheduler::readwrite_callback(void *userdata) {
    auto *sched = static_cast<Scheduler *>(userdata);
    sched->run_ready(true);
    return 0;
}

inline int Scheduler::readonly_callback(void *userdata) {
    auto *sched = static_cast<Scheduler *>(userdata);
    sched->in_readonly_ = true;
    sched->run_ready(false);
    sched->in_readonly_ = false;
    if (sched->need_rw_after_ro_) {
        sched->need_rw_after_ro_ = false;
        gpi_register_nexttime_callback(&Scheduler::nexttime_rw_callback, sched);
    }
    return 0;
}

inline int Scheduler::nexttime_rw_callback(void *userdata) {
    auto *sched = static_cast<Scheduler *>(userdata);
    sched->request_readwrite_callback();
    return 0;
}

inline void Scheduler::schedule_after_time(std::coroutine_handle<> handle,
                                           uint64_t delay) {
    auto *cb = new BaseCallback();
    cb->sched = this;
    cb->coro = TaskHandle::from_address(const_cast<void *>(handle.address()));
    cb->cb_handle = gpi_register_timed_callback(&Scheduler::timer_callback, cb,
                                                delay);
    if (!cb->cb_handle) {
        std::cerr << "Failed to register timed callback" << std::endl;
        delete cb;
        enqueue_ready(handle);
    }
}

inline void Scheduler::schedule_on_edge(std::coroutine_handle<> handle,
                                        gpi_sim_hdl signal, gpi_edge edge) {
    // std::cout << "Schedule on edge" << std::endl;
    auto *cb = new EdgeCallback();
    cb->sched = this;
    cb->coro = TaskHandle::from_address(const_cast<void *>(handle.address()));
    cb->signal = signal;
    cb->edge = edge;
    cb->cb_handle =
        gpi_register_value_change_callback(&Scheduler::edge_callback, cb, signal,
                                           edge);
    if (!cb->cb_handle) {
        std::cerr << "Failed to register value change callback" << std::endl;
        delete cb;
        enqueue_ready(handle);
    }
}

inline bool register_test(const std::string &name, test_fn fn) {
    Scheduler::instance().register_test(name, fn);
    return true;
}

#define COCOTB_TEST(name)                                                     \
    task<> name(cocotb::Dut &);                                               \
    static bool name##_registered = ::cocotb::register_test(#name, &name);

class JoinHandle {
public:
    explicit JoinHandle(task<>::handle_type handle) : handle_(handle) {}
    JoinHandle(JoinHandle &&other) noexcept
        : handle_(other.handle_), joined_(other.joined_) {
        other.handle_ = {};
        other.joined_ = false;
    }
    JoinHandle &operator=(JoinHandle &&other) noexcept {
        if (this != &other) {
            cleanup();
            handle_ = other.handle_;
            joined_ = other.joined_;
            other.handle_ = {};
            other.joined_ = false;
        }
        return *this;
    }
    JoinHandle(const JoinHandle &) = delete;
    JoinHandle &operator=(const JoinHandle &) = delete;

    ~JoinHandle() { cleanup(); }

    auto join() {
        joined_ = true;
        return task<>::join_awaiter{handle_};
    }

private:
    void cleanup() {
        if (!handle_) {
            return;
        }
        if (!joined_) {
            // Signal cancellation; scheduler will destroy when it next sees it.
            handle_.promise().cancelled = true;
        }
        handle_ = {};
    }

    task<>::handle_type handle_{};
    bool joined_{false};
};

template <class T>
inline JoinHandle start_soon(T &&t) {
    auto handle = std::move(t).release();
    Scheduler::instance().schedule_handle(handle);
    return JoinHandle(handle);
}

inline void Scheduler::run_next_test() {
    if (!dut_) {
        return;
    }
    if (next_test_index_ >= tests_.size()) {
        LOG_INFO("CPP Coroutine: All tests finished");
        return;
    }
    auto idx = next_test_index_++;
    auto t = tests_[idx].second(*dut_);
    t.detach();  // top-level tests clean themselves up
    schedule_task(std::move(t));
    run_ready();
}

inline Handle &Handle::operator=(int32_t value) {
    // std::cout << "Set Handle[" << gpi_get_signal_name_str(handle_) << "] = " << value << std::endl;
    if (!handle_) {
        std::cerr << "Attempted to drive an invalid handle" << std::endl;
        return *this;
    }
    Scheduler::instance().queue_write(handle_, value);
    return *this;
}

static int on_sim_start(void * /*cb_data*/, int /*argc*/,
                        char const *const * /*argv*/) {
    LOG_INFO("CPP Coroutine: Start of simulation");
    gpi_sim_hdl top = gpi_get_root_handle(nullptr);
    if (!top) {
        if (const char *env_top = std::getenv("TOPLEVEL")) {
            top = gpi_get_root_handle(env_top);
        }
    }

    if (!top) {
        std::cerr << "Failed to get root handle" << std::endl;
        return -1;
    }
    Scheduler::instance().set_dut_handle(top);
    Scheduler::instance().start_all_tests();
    return 0;
}

static void on_sim_end(void * /*cb_data*/) {
    LOG_INFO("CPP Coroutine: End of simulation");
}


enum class LogLevel {
    Info,
    Warn,
    Error
};

class Logger {
public:
    explicit Logger(std::string component)
        : component_(std::move(component)) {}

    void info(const std::string& message) {
        log(LogLevel::Info, message);
    }
    void log(LogLevel level, const std::string& message) {
        std::lock_guard<std::mutex> lock(mutex_);

        uint32_t high, low;
        gpi_get_sim_time(&high, &low);
        uint64_t time_val = (static_cast<uint64_t>(high) << 32) | low;
        double time_double = static_cast<double>(time_val);

        std::cout
            << std::right << std::fixed << std::setprecision(2) << std::setw(9) << time_double << "   "
            << std::left << std::setw(8) << level_to_string(level)
            << std::setw(35) << std::left << component_ << " "
            << message
            << '\n';
    }

private:
    static const char* level_to_string(LogLevel level) {
        switch (level) {
            case LogLevel::Info:  return "INFO     ";
            case LogLevel::Warn:  return "WARN     ";
            case LogLevel::Error: return "ERROR    ";
        }
        return "UNKNOWN  ";
    }

    std::string component_;
    std::chrono::steady_clock::time_point start_;
    std::mutex mutex_;
};

inline Logger log("cocotb");

}  // namespace cocotb

// Entry point function that will be called by GPI
// This function name should match what you specify in GPI_USERS
// NOTE: This is called during library initialization, so we can't access
// simulation objects here. We must register callbacks instead.
extern "C" void cocotb_entry_point() {
    if (!gpi_has_registered_impl()) {
        std::cerr << "Error: No GPI implementation registered" << std::endl;
        return;
    }

    if (gpi_register_start_of_sim_time_callback(&cocotb::on_sim_start, nullptr) !=
        0) {
        std::cerr << "Failed to register start of simulation callback"
                  << std::endl;
        return;
    }

    gpi_register_end_of_sim_time_callback(&cocotb::on_sim_end, nullptr);
    LOG_INFO("CPP Coroutine: Entry point registered");
}
