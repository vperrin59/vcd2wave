// SystemVerilog testbench to create VCD

module tb();

  logic clk = 0;
  logic rstn;


  logic start;
  logic ready;

  logic done;

  enum logic [1:0] {
    CMD_A = 2'b00,
    CMD_B = 2'b01,
    CMD_C = 2'b10,
    CMD_D = 2'b11
  } cmd;

  always
    clk = #5ns ~clk;

  initial begin
    rstn = 0;

    #7ns

    rstn = 1;
  end

  initial begin
    $dumpfile("dump.vcd");
    $dumpvars(0, tb);
    start <= 0;
    ready <= 1;
    done  <= 0;
    cmd   <= CMD_A;

    wait(rstn == 1'b1);

    @(posedge clk);
    start <= 1;
    cmd   <= CMD_B;

    @(posedge clk);
    start <= 0;
    ready <= 0;


    repeat(10)
      @(posedge clk);

    done <= 1;
    ready <= 1;

    repeat(2)
      @(posedge clk);

    $finish;
  end

endmodule